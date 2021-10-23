from __future__ import annotations

from base64 import urlsafe_b64encode
from datetime import timedelta
from functools import cached_property
from itertools import chain
from typing import List, Tuple
from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

import log
import requests

from ballotbuddies.core.helpers import send_invite_email

from .types import Progress


class VoterManager(models.Manager):
    def from_email(self, email: str, referrer: str) -> Voter:
        user, created = User.objects.get_or_create(
            email=email, defaults=dict(username=email)
        )
        if created:
            log.info(f"Created user: {user}")

        voter = self.from_user(user)

        if other := self.filter(slug=referrer).first():
            other.friends.add(voter)
            other.save()

            voter.referrer = voter.referrer or other
            voter.friends.add(other)
            voter.save()

        return voter

    def from_user(self, user: User) -> Voter:
        voter, created = self.get_or_create(user=user)
        if created:
            log.info(f"Created voter: {voter}")
        return voter

    def invite(self, voter: Voter, emails: List[str]) -> List[Voter]:
        friends = []
        for email in emails:
            user, created = User.objects.get_or_create(
                email=email, defaults=dict(username=email)
            )
            if created:
                log.info(f"Created user: {user}")
                send_invite_email(user, voter.user)

            other = self.from_user(user)
            other.referrer = other.referrer or voter
            other.friends.add(voter)
            other.save()

            voter.friends.add(other)
            friends.append(other)

        voter.save()
        return friends


class Voter(models.Model):

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    slug = models.CharField(max_length=100, blank=True)

    birth_date = models.DateField(null=True, blank=True)
    zip_code = models.CharField(
        null=True, blank=True, max_length=5, verbose_name="ZIP code"
    )

    status = models.JSONField(null=True, blank=True)
    updated = models.DateTimeField(null=True, blank=True)

    referrer = models.ForeignKey(
        "Voter", null=True, blank=True, on_delete=models.SET_NULL
    )
    friends = models.ManyToManyField("Voter", blank=True, related_name="followers")
    neighbors = models.ManyToManyField("Voter", blank=True, related_name="lurkers")
    strangers = models.ManyToManyField("Voter", blank=True, related_name="blockers")

    objects = VoterManager()

    def __str__(self):
        return f"{self.user.full_name} ({self.user.email})"

    @cached_property
    def email(self) -> str:
        return self.user.email

    @cached_property
    def first_name(self) -> str:
        return self.user.first_name

    @cached_property
    def last_name(self) -> str:
        return self.user.last_name

    @cached_property
    def display_name(self) -> str:
        return self.user.display_name

    @cached_property
    def data(self) -> dict:
        return dict(
            first_name=self.first_name,
            last_name=self.last_name,
            birth_date=self.birth_date,
            zip_code=self.zip_code,
        )

    @cached_property
    def complete(self) -> bool:
        return all(self.data.values())

    @cached_property
    def progress(self) -> Progress:
        status = self.status.get("status") if self.status else None
        return Progress.parse(status)

    @cached_property
    def community(self) -> chain[Voter]:
        # TODO: sort voters by progress
        return chain(self.friends.all(), self.neighbors.all())

    def update_status(self) -> Tuple[bool, str]:
        previous_status = self._status

        url = settings.MICHIGAN_ELECTIONS_API + "?" + urlencode(self.data)
        log.info(f"GET {url}")
        response = requests.get(url)
        if response.status_code == 202:
            data = response.json()
            log.error(f"{response.status_code} response: {data}")
            self.updated = timezone.now()
            return False, data["message"]
        if response.status_code != 200:
            log.error(f"{response.status_code} response")
            return False, ""

        data = response.json()
        log.info(f"{response.status_code} response: {data}")
        self.status = data
        self.updated = timezone.now()

        return self._status != previous_status, ""

    @property
    def _status(self) -> str:
        return (self.status or {}).get("id", "")

    def update_neighbors(self) -> int:
        added = 0
        for friend in self.friends.all():
            for neighbor in friend.friends.all():
                if not any(
                    (
                        neighbor == self,
                        self.friends.filter(pk=neighbor.pk).exists(),
                        self.neighbors.filter(pk=neighbor.pk).exists(),
                        self.strangers.filter(pk=neighbor.pk).exists(),
                    )
                ):
                    self.neighbors.add(neighbor)
                    added += 1
        return added

    @property
    def updated_humanized(self) -> str:
        if self.updated:
            delta = timezone.now() - self.updated
            if delta < timedelta(seconds=5):
                return "Now"
            if delta < timedelta(minutes=5):
                return "Today"
            return f"{self.updated:%-m/%d}"
        return "−"

    def save(self, **kwargs):
        self.slug = self._slugify()
        if self.id:
            self.friends.remove(self)
        super().save(**kwargs)

    def _slugify(self) -> str:
        fingerprint = self.first_name + self.last_name + str(self.zip_code)
        return urlsafe_b64encode(fingerprint.encode()).decode().strip("=")
