"""Tests for MeetingNotes."""
import pytest

from lidco.notion.meetings import ActionItem, Meeting, MeetingNotes


class TestMeetingNotesCreate:
    def test_create_returns_meeting(self):
        mn = MeetingNotes()
        m = mn.create("Standup", ["Alice", "Bob"])
        assert isinstance(m, Meeting)
        assert m.title == "Standup"
        assert m.attendees == ["Alice", "Bob"]

    def test_create_empty_title_raises(self):
        mn = MeetingNotes()
        with pytest.raises(ValueError, match="Title"):
            mn.create("  ")

    def test_create_no_attendees(self):
        mn = MeetingNotes()
        m = mn.create("Solo Meeting")
        assert m.attendees == []

    def test_create_generates_unique_ids(self):
        mn = MeetingNotes()
        m1 = mn.create("A")
        m2 = mn.create("B")
        assert m1.id != m2.id

    def test_get_existing_meeting(self):
        mn = MeetingNotes()
        m = mn.create("Test")
        fetched = mn.get(m.id)
        assert fetched.title == "Test"

    def test_get_nonexistent_raises(self):
        mn = MeetingNotes()
        with pytest.raises(KeyError, match="not found"):
            mn.get("bad_id")


class TestMeetingNotesAddNotes:
    def test_add_notes_appends_text(self):
        mn = MeetingNotes()
        m = mn.create("Meeting")
        mn.add_notes(m.id, "First note")
        mn.add_notes(m.id, "Second note")
        meeting = mn.get(m.id)
        assert "First note" in meeting.notes
        assert "Second note" in meeting.notes

    def test_add_notes_nonexistent_raises(self):
        mn = MeetingNotes()
        with pytest.raises(KeyError):
            mn.add_notes("bad_id", "text")

    def test_add_notes_separator(self):
        mn = MeetingNotes()
        m = mn.create("Meeting")
        mn.add_notes(m.id, "line1")
        mn.add_notes(m.id, "line2")
        meeting = mn.get(m.id)
        assert "\n" in meeting.notes


class TestMeetingNotesActionItems:
    def test_extract_checkbox_items(self):
        mn = MeetingNotes()
        m = mn.create("Meeting")
        mn.add_notes(m.id, "- [ ] Buy groceries\n- [ ] Fix bug")
        items = mn.extract_action_items(m.id)
        assert len(items) == 2
        assert items[0].text == "Buy groceries"
        assert items[1].text == "Fix bug"

    def test_extract_todo_items(self):
        mn = MeetingNotes()
        m = mn.create("Meeting")
        mn.add_notes(m.id, "- TODO: Write tests")
        items = mn.extract_action_items(m.id)
        assert len(items) == 1
        assert "Write tests" in items[0].text

    def test_extract_action_colon_items(self):
        mn = MeetingNotes()
        m = mn.create("Meeting")
        mn.add_notes(m.id, "ACTION: Deploy to staging")
        items = mn.extract_action_items(m.id)
        assert len(items) == 1
        assert "Deploy to staging" in items[0].text

    def test_extract_no_items(self):
        mn = MeetingNotes()
        m = mn.create("Meeting")
        mn.add_notes(m.id, "Just normal discussion text")
        items = mn.extract_action_items(m.id)
        assert items == []

    def test_extract_stores_items_on_meeting(self):
        mn = MeetingNotes()
        m = mn.create("Meeting")
        mn.add_notes(m.id, "- [ ] Task A")
        mn.extract_action_items(m.id)
        meeting = mn.get(m.id)
        assert len(meeting.action_items) == 1

    def test_extract_nonexistent_raises(self):
        mn = MeetingNotes()
        with pytest.raises(KeyError):
            mn.extract_action_items("bad")


class TestMeetingNotesAssign:
    def test_assign_followup_success(self):
        mn = MeetingNotes()
        m = mn.create("Meeting")
        mn.add_notes(m.id, "- [ ] Review PR")
        mn.extract_action_items(m.id)
        ok = mn.assign_followup(m.id, "Review PR", "Alice")
        assert ok is True
        meeting = mn.get(m.id)
        assert meeting.action_items[0].assignee == "Alice"

    def test_assign_followup_not_found(self):
        mn = MeetingNotes()
        m = mn.create("Meeting")
        mn.add_notes(m.id, "- [ ] Task A")
        mn.extract_action_items(m.id)
        ok = mn.assign_followup(m.id, "Nonexistent task", "Bob")
        assert ok is False

    def test_assign_nonexistent_meeting_raises(self):
        mn = MeetingNotes()
        with pytest.raises(KeyError):
            mn.assign_followup("bad", "item", "person")


class TestMeetingNotesList:
    def test_list_meetings_empty(self):
        mn = MeetingNotes()
        assert mn.list_meetings() == []

    def test_list_meetings_returns_all(self):
        mn = MeetingNotes()
        mn.create("A")
        mn.create("B")
        assert len(mn.list_meetings()) == 2

    def test_list_meetings_newest_first(self):
        mn = MeetingNotes()
        m1 = mn.create("First")
        m2 = mn.create("Second")
        meetings = mn.list_meetings()
        assert meetings[0].title == "Second"
