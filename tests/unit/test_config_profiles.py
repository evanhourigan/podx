#!/usr/bin/env python3
"""Tests for configuration profiles."""

import tempfile
from pathlib import Path

import pytest

from podx.config import (
    ConfigProfile,
    ProfileManager,
    get_builtin_profiles,
    install_builtin_profiles,
)


class TestConfigProfile:
    """Test ConfigProfile class."""

    def test_create_profile(self):
        """Test creating a profile."""
        profile = ConfigProfile(
            name="test",
            settings={"asr_model": "large-v3", "diarize": True},
            description="Test profile",
        )

        assert profile.name == "test"
        assert profile.description == "Test profile"
        assert profile.settings["asr_model"] == "large-v3"
        assert profile.settings["diarize"] is True

    def test_to_dict(self):
        """Test converting profile to dictionary."""
        profile = ConfigProfile(name="test", settings={"key": "value"}, description="desc")

        data = profile.to_dict()

        assert data["name"] == "test"
        assert data["description"] == "desc"
        assert data["settings"] == {"key": "value"}

    def test_from_dict(self):
        """Test creating profile from dictionary."""
        data = {
            "name": "test",
            "description": "Test profile",
            "settings": {"asr_model": "large-v3"},
        }

        profile = ConfigProfile.from_dict(data)

        assert profile.name == "test"
        assert profile.description == "Test profile"
        assert profile.settings["asr_model"] == "large-v3"

    def test_from_dict_without_description(self):
        """Test creating profile from dict without description."""
        data = {"name": "test", "settings": {"key": "value"}}

        profile = ConfigProfile.from_dict(data)

        assert profile.name == "test"
        assert profile.description == ""
        assert profile.settings["key"] == "value"


class TestProfileManager:
    """Test ProfileManager class."""

    @pytest.fixture
    def temp_profile_dir(self):
        """Create temporary profile directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def manager(self, temp_profile_dir):
        """Create profile manager with temp directory."""
        return ProfileManager(temp_profile_dir)

    def test_save_and_load(self, manager):
        """Test saving and loading a profile."""
        profile = ConfigProfile(
            name="test",
            settings={"asr_model": "large-v3", "diarize": True},
            description="Test profile",
        )

        # Save
        manager.save(profile)

        # Load
        loaded = manager.load("test")

        assert loaded is not None
        assert loaded.name == "test"
        assert loaded.description == "Test profile"
        assert loaded.settings["asr_model"] == "large-v3"
        assert loaded.settings["diarize"] is True

    def test_load_nonexistent(self, manager):
        """Test loading a profile that doesn't exist."""
        loaded = manager.load("nonexistent")
        assert loaded is None

    def test_list_profiles(self, manager):
        """Test listing profiles."""
        # Initially empty
        assert manager.list_profiles() == []

        # Save some profiles
        manager.save(ConfigProfile("profile1", {"key": "value1"}))
        manager.save(ConfigProfile("profile2", {"key": "value2"}))
        manager.save(ConfigProfile("profile3", {"key": "value3"}))

        # List should return sorted names
        profiles = manager.list_profiles()
        assert profiles == ["profile1", "profile2", "profile3"]

    def test_delete(self, manager):
        """Test deleting a profile."""
        profile = ConfigProfile("test", {"key": "value"})
        manager.save(profile)

        # Verify it exists
        assert "test" in manager.list_profiles()

        # Delete
        result = manager.delete("test")
        assert result is True

        # Verify it's gone
        assert "test" not in manager.list_profiles()
        assert manager.load("test") is None

    def test_delete_nonexistent(self, manager):
        """Test deleting a profile that doesn't exist."""
        result = manager.delete("nonexistent")
        assert result is False

    def test_save_invalid_name(self, manager):
        """Test saving profile with invalid name."""
        profile = ConfigProfile("test/invalid", {"key": "value"})

        with pytest.raises(ValueError, match="Invalid profile name"):
            manager.save(profile)

    def test_export_profile(self, manager):
        """Test exporting profile as YAML."""
        profile = ConfigProfile(name="test", settings={"asr_model": "large-v3"}, description="Test")
        manager.save(profile)

        yaml_content = manager.export_profile("test")

        assert yaml_content is not None
        assert "name: test" in yaml_content
        assert "description: Test" in yaml_content
        assert "asr_model: large-v3" in yaml_content

    def test_export_nonexistent(self, manager):
        """Test exporting nonexistent profile."""
        yaml_content = manager.export_profile("nonexistent")
        assert yaml_content is None

    def test_import_profile(self, manager):
        """Test importing profile from YAML."""
        yaml_content = """
name: imported
description: Imported profile
settings:
  asr_model: large-v3
  diarize: true
"""

        profile = manager.import_profile(yaml_content)

        assert profile.name == "imported"
        assert profile.description == "Imported profile"
        assert profile.settings["asr_model"] == "large-v3"
        assert profile.settings["diarize"] is True

        # Verify it was saved
        loaded = manager.load("imported")
        assert loaded is not None
        assert loaded.name == "imported"

    def test_import_invalid_yaml(self, manager):
        """Test importing invalid YAML."""
        with pytest.raises(ValueError, match="Failed to import profile"):
            manager.import_profile("invalid: yaml: content:")


class TestBuiltinProfiles:
    """Test built-in profile functionality."""

    def test_get_builtin_profiles(self):
        """Test getting built-in profiles."""
        profiles = get_builtin_profiles()

        assert len(profiles) == 3

        names = [p.name for p in profiles]
        assert "quick" in names
        assert "standard" in names
        assert "high-quality" in names

        # Check quick profile
        quick = next(p for p in profiles if p.name == "quick")
        assert quick.settings["asr_model"] == "base"
        assert quick.settings["diarize"] is False
        assert quick.settings["deepcast"] is False

        # Check high-quality profile
        hq = next(p for p in profiles if p.name == "high-quality")
        assert hq.settings["asr_model"] == "large-v3"
        assert hq.settings["diarize"] is True
        assert hq.settings["deepcast"] is True
        assert "pdf" in hq.settings["export_formats"]
        assert "html" in hq.settings["export_formats"]

    def test_install_builtin_profiles(self):
        """Test installing built-in profiles."""
        with tempfile.TemporaryDirectory() as tmpdir:
            profile_dir = Path(tmpdir)

            count = install_builtin_profiles(profile_dir)

            assert count == 3

            manager = ProfileManager(profile_dir)
            profiles = manager.list_profiles()

            assert "quick" in profiles
            assert "standard" in profiles
            assert "high-quality" in profiles

            # Verify they can be loaded
            quick = manager.load("quick")
            assert quick is not None
            assert quick.settings["asr_model"] == "base"
