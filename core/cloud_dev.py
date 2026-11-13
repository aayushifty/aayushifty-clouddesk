"""
Cloud Development & Workspaces Module - Aayushifty CloudDesk
Integrates Google Colab, GitHub repositories, GitHub Codespaces, and local projects.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional


class CloudDevManager:
    """Manages cloud offloading (Colab, Codespaces) and local project discovery."""

    @staticmethod
    def get_github_status() -> Dict[str, Any]:
        """Checks GitHub CLI authentication and active account."""
        if not shutil.which("gh"):
            return {"installed": False, "authenticated": False, "error": "gh CLI not found"}

        try:
            res = subprocess.run(
                ["gh", "auth", "status"],
                capture_output=True, text=True, check=False
            )
            output = res.stdout + res.stderr
            is_logged_in = "Logged in to" in output or "Active account: true" in output

            # Extract user name if possible
            account = "Unknown"
            for line in output.splitlines():
                if "account" in line.lower():
                    account = line.strip()
                    break

            return {
                "installed": True,
                "authenticated": is_logged_in,
                "account_details": account,
                "raw_status": output.strip()
            }
        except Exception as e:
            return {"installed": True, "authenticated": False, "error": str(e)}

    @staticmethod
    def get_user_repositories(limit: int = 15) -> List[Dict[str, Any]]:
        """Fetches the user's latest GitHub repositories via GitHub CLI."""
        if not shutil.which("gh"):
            return []

        try:
            res = subprocess.run(
                ["gh", "repo", "list", "--limit", str(limit), "--json", "name,description,url,isPrivate,updatedAt,pushedAt"],
                capture_output=True, text=True, check=False
            )
            if res.returncode == 0 and res.stdout.strip():
                return json.loads(res.stdout)
            return []
        except Exception:
            return []

    @staticmethod
    def get_codespaces() -> List[Dict[str, Any]]:
        """Lists active GitHub Codespaces for the authenticated user."""
        if not shutil.which("gh"):
            return []

        try:
            res = subprocess.run(
                ["gh", "codespace", "list", "--json", "name,repository,state,gitStatus"],
                capture_output=True, text=True, check=False
            )
            if res.returncode == 0 and res.stdout.strip():
                return json.loads(res.stdout)
            return []
        except Exception:
            return []

    @staticmethod
    def discover_local_projects() -> List[Dict[str, Any]]:
        """
        Discovers local development projects across common workspaces.
        Detects technology stack (React, Node, Python, ESP32/PlatformIO, Arduino).
        """
        search_roots = [
            Path("C:/Users/joshi/.gemini/antigravity/scratch"),
            Path("C:/Users/joshi/code"),
            Path("C:/Users/joshi/AETHER"),
            Path("C:/Users/joshi/FORGE"),
            Path("C:/Users/joshi/HandChord"),
            Path("C:/Users/joshi/offlinepay"),
            Path("C:/Users/joshi/OpenJarvis"),
            Path("D:/Projects")
        ]

        projects = []
        for root in search_roots:
            if not root.exists():
                continue

            # If root is itself a project
            dirs_to_check = [root]
            # If root is a workspace directory containing subprojects
            if root.name in ("scratch", "code", "Projects"):
                try:
                    dirs_to_check.extend([d for d in root.iterdir() if d.is_dir()])
                except Exception:
                    pass

            for p in dirs_to_check:
                if not p.is_dir() or p.name.startswith("."):
                    continue

                # Detect stack
                stack = []
                if (p / "package.json").exists():
                    stack.append("Node.js")
                    try:
                        content = (p / "package.json").read_text(encoding="utf-8", errors="ignore")
                        if "react" in content.lower():
                            stack.append("React")
                        if "vite" in content.lower():
                            stack.append("Vite")
                    except Exception:
                        pass

                if any(p.glob("*.py")) or (p / "requirements.txt").exists() or (p / "pyproject.toml").exists():
                    stack.append("Python")

                if (p / "platformio.ini").exists() or any(p.glob("*.ino")):
                    stack.append("ESP32/Arduino")

                if (p / "Cargo.toml").exists():
                    stack.append("Rust")

                # If stack identified or git repo
                is_git = (p / ".git").exists()
                if stack or is_git:
                    projects.append({
                        "name": p.name,
                        "path": str(p),
                        "stack": stack if stack else ["General Project"],
                        "is_git": is_git,
                        "has_node_modules": (p / "node_modules").exists(),
                        "has_venv": (p / ".venv").exists() or (p / "venv").exists()
                    })

        # Remove duplicates
        seen = set()
        unique = []
        for proj in projects:
            if proj["path"] not in seen:
                seen.add(proj["path"])
                unique.append(proj)

        return unique

    @staticmethod
    def generate_colab_template(output_path: Path) -> Path:
        """Generates a production-grade Google Colab starter notebook with Google Drive integration."""
        nb_content = {
            "nbformat": 4,
            "nbformat_minor": 0,
            "metadata": {
                "colab": {
                    "name": "Aayushifty_CloudDesk_ML_Accelerator.ipynb",
                    "provenance": [],
                    "gpuType": "T4"
                },
                "kernelspec": {
                    "name": "python3",
                    "display_name": "Python 3"
                },
                "language_info": {
                    "name": "python"
                },
                "accelerator": "GPU"
            },
            "cells": [
                {
                    "cell_type": "markdown",
                    "metadata": {},
                    "source": [
                        "# Aayushifty CloudDesk — Cloud ML & Heavy Compute Accelerator\n",
                        "**Hybrid Cloud Integration: Local Laptop (8 GB RAM) <-> Google Colab (Free GPU / 12 GB+ RAM)**\n\n",
                        "This notebook seamlessly bridges your local Windows development workflow with Google Cloud.\n",
                        "It connects directly to your Google Drive unified folders without downloading files locally."
                    ]
                },
                {
                    "cell_type": "code",
                    "execution_count": None,
                    "metadata": {},
                    "outputs": [],
                    "source": [
                        "# 1. Mount Google Drive\n",
                        "from google.colab import drive\n",
                        "import os\n",
                        "import sys\n",
                        "\n",
                        "print('Mounting Google Drive...')\n",
                        "drive.mount('/content/drive')\n",
                        "\n",
                        "# CloudDesk Unified Paths\n",
                        "CLOUDDESK_ROOT = '/content/drive/MyDrive'\n",
                        "MODELS_DIR = os.path.join(CLOUDDESK_ROOT, 'AI_Models')\n",
                        "DATASETS_DIR = os.path.join(CLOUDDESK_ROOT, 'Datasets')\n",
                        "PROJECTS_DIR = os.path.join(CLOUDDESK_ROOT, 'Projects')\n",
                        "ASSETS_DIR = os.path.join(CLOUDDESK_ROOT, 'Development_Assets')\n",
                        "\n",
                        "print('\\n=== CLOUDDESK STATUS ===')\n",
                        "print(f'Datasets Directory: {DATASETS_DIR} (Exists: {os.path.exists(DATASETS_DIR)})')\n",
                        "print(f'AI Models Directory: {MODELS_DIR} (Exists: {os.path.exists(MODELS_DIR)})')\n",
                        "print(f'Projects Directory: {PROJECTS_DIR} (Exists: {os.path.exists(PROJECTS_DIR)})')"
                    ]
                },
                {
                    "cell_type": "code",
                    "execution_count": None,
                    "metadata": {},
                    "outputs": [],
                    "source": [
                        "# 2. Inspect GPU & System Hardware\n",
                        "!nvidia-smi"
                    ]
                },
                {
                    "cell_type": "code",
                    "execution_count": None,
                    "metadata": {},
                    "outputs": [],
                    "source": [
                        "# 3. Heavy Compute Sandbox\n",
                        "# Run heavy PyTorch training, fine-tuning, or inference here:\n",
                        "import torch\n",
                        "print(f'CUDA Available: {torch.cuda.is_available()}')\n",
                        "if torch.cuda.is_available():\n",
                        "    print(f'Device Name: {torch.cuda.get_device_name(0)}')\n",
                        "    print(f'VRAM Allocated: {torch.cuda.memory_allocated() / (1024**2):.2f} MB')\n"
                    ]
                }
            ]
        }
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(nb_content, indent=2), encoding="utf-8")
        return output_path

