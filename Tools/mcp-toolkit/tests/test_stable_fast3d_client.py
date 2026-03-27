import asyncio

from veilbreakers_mcp.shared.stable_fast3d_client import StableFast3DGenerator


def test_stable_fast3d_generator_fails_cleanly_for_missing_repo(tmp_path):
    generator = StableFast3DGenerator(repo_path=str(tmp_path / "missing_repo"))
    image_path = tmp_path / "image.png"
    image_path.write_bytes(b"fake")

    result = asyncio.run(
        generator.generate_from_image(
            image_path=str(image_path),
            output_dir=str(tmp_path / "out"),
        )
    )

    assert result["status"] == "failed"
    assert "repo not found" in result["error"].lower()
