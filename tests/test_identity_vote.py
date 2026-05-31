from __future__ import annotations

from pi_face_greeter.app.identity_vote import PENDING, IdentityVoter


def test_identity_voter_confirms_after_required_streak() -> None:
    voter = IdentityVoter(required=3)
    assert voter.push("Todd") is PENDING
    assert voter.push("Todd") is PENDING
    assert voter.push("Todd") == "Todd"


def test_identity_voter_resets_streak_on_change() -> None:
    voter = IdentityVoter(required=3)
    voter.push("Todd")
    voter.push("Todd")
    assert voter.push("Jane") is PENDING
    assert voter.push("Jane") is PENDING
    assert voter.push("Jane") == "Jane"


def test_identity_voter_confirms_unknown_identity() -> None:
    voter = IdentityVoter(required=2)
    assert voter.push(None) is PENDING
    assert voter.push(None) is None


def test_identity_voter_reset_clears_streak() -> None:
    voter = IdentityVoter(required=2)
    voter.push("Todd")
    voter.reset()
    assert voter.push("Todd") is PENDING
