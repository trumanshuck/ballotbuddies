# pylint: disable=redefined-outer-name,unused-variable,unused-argument,expression-not-assigned

from django.utils import timezone

import pytest

from ..constants import VOTED
from ..models import Voter


@pytest.fixture
def voter(admin_user):
    admin_user.first_name = "Jane"
    admin_user.last_name = "Doe"
    admin_user.save()
    return Voter.objects.from_user(admin_user, VOTED.status)


@pytest.fixture
def complete_voter(voter):
    voter.birth_date = timezone.now()
    voter.zip_code = "12345"
    voter.save()
    return voter


@pytest.mark.django_db
def describe_index():
    def it_disables_buttons_when_unauthenticated(expect, client, voter):
        response = client.get("/")

        html = response.content.decode()
        expect(html).excludes("View Profile")
        expect(html.count("disabled")) == 4

    def it_disables_buttons_with_referrer(expect, client, voter):
        client.force_login(voter.user)

        response = client.get(f"/?referrer={voter.slug}")

        html = response.content.decode()
        expect(html).excludes("View Profile")
        expect(html.count("disabled")) >= 4  # TODO: should be 5 including the voter


@pytest.mark.django_db
def describe_profile():
    def it_redirects_to_finish_setup(expect, client, voter):
        client.force_login(voter.user)

        response = client.get("/profile/")
        expect(response.url) == "/profile/setup/"

    def it_can_update_reminder_emails_preference(expect, client, complete_voter):
        client.force_login(complete_voter.user)

        response = client.get("/profile/")
        html = response.content.decode()
        expect(html).contains("checked")

        response = client.post("/profile/", follow=True)
        html = response.content.decode()
        expect(html).excludes("checked")

        response = client.post("/profile/", follow=True)
        html = response.content.decode()
        expect(html).contains("checked")


@pytest.mark.vcr
@pytest.mark.django_db
def describe_status():
    @pytest.fixture
    def url(voter):
        return f"/friends/{voter.slug}/_status"

    def it_can_manually_record_voting(expect, client, url, voter):
        client.force_login(voter.user)

        response = client.post(url, {"voted": True})

        html = response.content.decode()
        expect(html).includes("Didn't vote")

    def it_can_manually_clear_voting(expect, client, url, voter):
        client.force_login(voter.user)

        response = client.post(url, {"reset": True})

        html = response.content.decode()
        expect(html).excludes("Didn't vote")
