"""Tests for Q243 VirtualMemory."""
from __future__ import annotations

import time
from unittest.mock import patch

import pytest

from lidco.context.virtual_memory import Page, VirtualMemory


class TestVirtualMemoryAddPage:
    def test_add_page(self):
        vm = VirtualMemory()
        vm.add_page("p1", "hello")
        assert vm.get_page("p1") is not None
        assert vm.get_page("p1").content == "hello"

    def test_add_page_is_in_memory(self):
        vm = VirtualMemory()
        vm.add_page("p1", "hello")
        assert vm.get_page("p1").in_memory is True

    def test_add_multiple_pages(self):
        vm = VirtualMemory()
        vm.add_page("p1", "a")
        vm.add_page("p2", "b")
        assert len(vm.working_set()) == 2


class TestVirtualMemoryPageOut:
    def test_page_out(self):
        vm = VirtualMemory()
        vm.add_page("p1", "content")
        assert vm.page_out("p1") is True
        assert vm.get_page("p1").in_memory is False

    def test_page_out_missing(self):
        vm = VirtualMemory()
        assert vm.page_out("nope") is False

    def test_page_out_already_out(self):
        vm = VirtualMemory()
        vm.add_page("p1", "content")
        vm.page_out("p1")
        assert vm.page_out("p1") is False

    def test_page_out_updates_stats(self):
        vm = VirtualMemory()
        vm.add_page("p1", "content")
        vm.page_out("p1")
        assert vm.stats()["page_out_count"] == 1


class TestVirtualMemoryPageIn:
    def test_page_in_from_disk(self):
        vm = VirtualMemory()
        vm.add_page("p1", "content")
        vm.page_out("p1")
        result = vm.page_in("p1")
        assert result == "content"
        assert vm.get_page("p1").in_memory is True

    def test_page_in_already_in_memory(self):
        vm = VirtualMemory()
        vm.add_page("p1", "content")
        result = vm.page_in("p1")
        assert result == "content"

    def test_page_in_missing(self):
        vm = VirtualMemory()
        assert vm.page_in("nope") is None

    def test_page_in_updates_stats(self):
        vm = VirtualMemory()
        vm.add_page("p1", "content")
        vm.page_out("p1")
        vm.page_in("p1")
        assert vm.stats()["page_in_count"] == 1


class TestVirtualMemoryAccess:
    def test_access_in_memory(self):
        vm = VirtualMemory()
        vm.add_page("p1", "content")
        assert vm.access("p1") == "content"

    def test_access_pages_in_from_disk(self):
        vm = VirtualMemory()
        vm.add_page("p1", "content")
        vm.page_out("p1")
        assert vm.access("p1") == "content"
        assert vm.get_page("p1").in_memory is True

    def test_access_missing(self):
        vm = VirtualMemory()
        assert vm.access("nope") is None

    def test_access_updates_last_accessed(self):
        vm = VirtualMemory()
        vm.add_page("p1", "content")
        old_time = vm.get_page("p1").last_accessed
        time.sleep(0.01)
        vm.access("p1")
        assert vm.get_page("p1").last_accessed > old_time


class TestVirtualMemoryWorkingSet:
    def test_working_set_all_in_memory(self):
        vm = VirtualMemory()
        vm.add_page("p1", "a")
        vm.add_page("p2", "b")
        assert set(vm.working_set()) == {"p1", "p2"}

    def test_working_set_excludes_paged_out(self):
        vm = VirtualMemory()
        vm.add_page("p1", "a")
        vm.add_page("p2", "b")
        vm.page_out("p1")
        assert vm.working_set() == ["p2"]

    def test_working_set_empty(self):
        vm = VirtualMemory()
        assert vm.working_set() == []


class TestVirtualMemoryEvictLru:
    def test_evict_lru_removes_oldest(self):
        vm = VirtualMemory()
        vm.add_page("old", "a")
        time.sleep(0.01)
        vm.add_page("new", "b")
        evicted = vm.evict_lru()
        assert evicted == "old"
        assert vm.get_page("old").in_memory is False

    def test_evict_lru_empty(self):
        vm = VirtualMemory()
        assert vm.evict_lru() is None

    def test_evict_lru_all_paged_out(self):
        vm = VirtualMemory()
        vm.add_page("p1", "a")
        vm.page_out("p1")
        assert vm.evict_lru() is None


class TestVirtualMemoryStats:
    def test_stats_empty(self):
        vm = VirtualMemory()
        s = vm.stats()
        assert s["total_pages"] == 0
        assert s["in_memory"] == 0
        assert s["on_disk"] == 0

    def test_stats_mixed(self):
        vm = VirtualMemory()
        vm.add_page("p1", "a")
        vm.add_page("p2", "b")
        vm.page_out("p2")
        s = vm.stats()
        assert s["total_pages"] == 2
        assert s["in_memory"] == 1
        assert s["on_disk"] == 1
