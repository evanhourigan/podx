#!/usr/bin/env python3
"""Tests for CLI completion support."""

import pytest

from podx.cli.completion import get_completion_script, install_completion


class TestCompletionScripts:
    """Test completion script generation."""

    def test_bash_completion_script(self):
        """Test bash completion script generation."""
        script = get_completion_script("bash")

        assert script is not None
        assert "_podx_completion" in script
        assert "complete" in script
        assert "podx-transcribe" in script
        assert "podx-config" in script

    def test_zsh_completion_script(self):
        """Test zsh completion script generation."""
        script = get_completion_script("zsh")

        assert script is not None
        assert "#compdef" in script
        assert "_podx_completion" in script
        assert "podx-transcribe" in script
        assert "podx-config" in script

    def test_fish_completion_script(self):
        """Test fish completion script generation."""
        script = get_completion_script("fish")

        assert script is not None
        assert "_podx_completion" in script
        assert "complete" in script
        assert "podx-transcribe" in script
        assert "podx-config" in script

    def test_invalid_shell(self):
        """Test error on invalid shell."""
        with pytest.raises(ValueError, match="Unsupported shell"):
            get_completion_script("invalid")


class TestInstallCompletion:
    """Test completion installation instructions."""

    def test_bash_install_instructions(self):
        """Test bash installation instructions."""
        instructions = install_completion("bash")

        assert "Bash Completion Installation" in instructions
        assert "bash_completion.d" in instructions
        assert "bashrc" in instructions
        assert "source" in instructions

    def test_zsh_install_instructions(self):
        """Test zsh installation instructions."""
        instructions = install_completion("zsh")

        assert "Zsh Completion Installation" in instructions
        assert "zsh/completion" in instructions
        assert "zshrc" in instructions
        assert "fpath" in instructions
        assert "compinit" in instructions

    def test_fish_install_instructions(self):
        """Test fish installation instructions."""
        instructions = install_completion("fish")

        assert "Fish Completion Installation" in instructions
        assert "config/fish/completions" in instructions
        assert "exec fish" in instructions

    def test_invalid_shell_install(self):
        """Test error on invalid shell."""
        with pytest.raises(ValueError, match="Unsupported shell"):
            install_completion("invalid")
