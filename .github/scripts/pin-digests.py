#!/usr/bin/env python3
"""Write release-manifest.json with docker image digests."""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


def digest_for(image: str) -> str:
    """Get the digest for a docker image."""
    try:
        out = subprocess.check_output(
            ["docker", "image", "inspect", "--format", "{{index .RepoDigests 0}}", image],
            text=True,
        ).strip()
        return out or image
    except subprocess.CalledProcessError:
        # If image not found or no digest, return the image name
        return image


def main() -> None:
    """Main entry point."""
    p = argparse.ArgumentParser(description="Write release-manifest.json with docker image digests")
    p.add_argument("--sih-image", required=True, help="SIH docker image name")
    p.add_argument("--gazebo-image", required=True, help="Gazebo docker image name")
    p.add_argument("--out", type=Path, default=Path("release-manifest.json"), help="Output file path")
    args = p.parse_args()
    
    manifest = {
        "sim_sih": digest_for(args.sih_image),
        "sim_gazebo": digest_for(args.gazebo_image),
    }
    args.out.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "path": str(args.out)}))


if __name__ == "__main__":
    main()
