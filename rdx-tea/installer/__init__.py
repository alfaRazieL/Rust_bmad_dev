"""RDX-TEA project installer package (Wave 7).

Public entrypoints for installing / updating / uninstalling the shipped
surface into a user project. See ``project_installer`` for the contract.
"""

from __future__ import annotations

from .project_installer import (  # noqa: F401
    ISOLATION_SETTINGS,
    REQUIRED_SCRIPTS,
    WRAPPER_SKILLS,
    InstallerError,
    MissingProductionFileError,
    UserFileProtectedError,
    VersionRangeError,
    adapter_version,
    check_tea_version,
    install,
    source_inventory,
    supported_tea_bounds,
    uninstall,
    update,
    write_overlay,
)

__all__ = [
    "install",
    "update",
    "uninstall",
    "write_overlay",
    "check_tea_version",
    "source_inventory",
    "supported_tea_bounds",
    "adapter_version",
    "ISOLATION_SETTINGS",
    "REQUIRED_SCRIPTS",
    "WRAPPER_SKILLS",
    "InstallerError",
    "MissingProductionFileError",
    "UserFileProtectedError",
    "VersionRangeError",
]
