from __future__ import annotations

from contextlib import suppress
from datetime import timedelta
from typing import TYPE_CHECKING

from django.db import models
from django.utils import timezone

import log
from annoying.fields import AutoOneToOneField

if TYPE_CHECKING:
    from ballotbuddies.buddies.models import Voter


class Profile(models.Model):

    voter: Voter = AutoOneToOneField("buddies.Voter", on_delete=models.CASCADE)

    always_alert = models.BooleanField(default=False)
    never_alert = models.BooleanField(default=False)

    last_alerted = models.DateTimeField(auto_now_add=True)
    last_viewed = models.DateTimeField(auto_now_add=True)
    staleness = models.DurationField(default=timedelta(days=0), editable=False)
    will_alert = models.BooleanField(default=False, editable=False)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-staleness"]

    def __str__(self):
        return str(self.voter)

    def __repr__(self):
        return repr(self.voter)

    @property
    def message(self) -> Message:
        return Message.objects.get_draft(self)

    @property
    def can_alert(self) -> bool:
        return bool(self.message)

    @property
    def should_alert(self) -> bool:
        if self.never_alert:
            return False
        if self.always_alert:
            return True
        if self.voter.complete:
            if self.voter.progress.actions:
                if 0 < self.voter.progress.election.days < 7:
                    return self.staleness > timedelta(days=1)
                return self.staleness > timedelta(days=14)
            return self.staleness > timedelta(days=90)
        else:
            return self.staleness > timedelta(days=30)

    def alert(self, voter: Voter):
        self.message.add(voter)

    def mark_alerted(self, *, save=True):
        self.last_alerted = timezone.now()
        if save:
            self.message.mark_sent()
            self.save()

    def mark_viewed(self, *, save=True):
        self.last_viewed = timezone.now()
        if save:
            if not self.always_alert:
                self.message.mark_read()
            self.save()

    def _staleness(self) -> timedelta:
        now = timezone.now()
        self.last_alerted = self.last_alerted or now
        self.last_viewed = self.last_viewed or now
        delta = min(now - self.last_alerted, now - self.last_viewed)
        return timedelta(days=delta.days)

    def save(self, **kwargs):
        self.staleness = self._staleness()
        with suppress(ValueError):
            self.will_alert = self.can_alert and self.should_alert
        super().save(**kwargs)


class MessageManager(models.Manager):
    def get_draft(self, profile: Profile):
        created = False
        message = self.filter(profile=profile, sent=False).first()
        if not message:
            message, created = self.get_or_create(profile=profile, sent=False)
        if created:
            log.debug(f"Drafted new message: {message}")
        return message


class Message(models.Model):

    profile: Profile = models.ForeignKey(Profile, on_delete=models.CASCADE)  # type: ignore

    activity = models.JSONField(blank=True, default=dict)
    sent = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    sent_at = models.DateTimeField(null=True, blank=True, editable=False)

    objects = MessageManager()

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        sent = "Sent" if self.sent else "Draft"
        count = len(self.activity)
        activities = "Activity" if count == 1 else "Activities"
        return f"{sent}: {count} {activities}"

    def __bool__(self):
        return bool(self.activity)

    def __len__(self):
        return len(self.activity)

    @property
    def subject(self) -> str:
        days = self.profile.voter.progress.election.days
        if days == 1:
            _in_days = " Tomorrow"
        elif days > 0:
            _in_days = f" in {days} Days"
        else:
            _in_days = ""
        return f"Your Friends are Preparing to Vote{_in_days}"

    @property
    def body(self) -> str:
        # TODO: Move the HTML rendering to `emails/activity.html`
        count = len(self.activity)
        s = "" if count == 1 else "s"
        have = "has" if count == 1 else "have"
        if name := self.profile.voter.election:
            date = self.profile.voter.progress.election.date_humanized
            assert date
            _in_election = f" in the upcoming <b>{name}</b> election on <b>{date}</b>"
        else:
            _in_election = ""
        activity = "<li>" + "</li><li>".join(self.activity_lines) + "</li>"
        return (
            f"Your {count} friend{s} on Michigan <b>Ballot Buddies</b> {have} "
            f"been making progress towards casting their vote{_in_election}.\n\n"
            f"Here's what they've been up to:\n\n<ul>{activity}</ul>"
        )

    @property
    def activity_lines(self) -> list[str]:
        return list(self.activity.values())

    @property
    def dismissed(self) -> bool | None:
        if self.sent_at:
            return False
        if self.sent:
            return True
        return None

    def add(self, voter: Voter, *, save=True):
        self.activity[voter.id] = voter.activity
        if save:
            self.save()

    def clear(self):
        log.info(f"Clearing unset message to {self.profile}")
        self.activity = {}
        self.save()

    def mark_sent(self, *, save=True):
        self.sent = True
        self.sent_at = timezone.now()
        if save:
            self.save()

    def mark_read(self, *, save=True):
        self.sent = True
        if save:
            self.save()
