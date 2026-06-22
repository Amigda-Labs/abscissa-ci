from pathlib import Path

import pytest

from abscissa_ci.agents.area_agent import image_to_data_url


def test_image_to_data_url_rejects_unsupported_file_type(tmp_path: Path) -> None:
    path = tmp_path / "plan.pdf"
    path.write_bytes(b"%PDF")

    with pytest.raises(ValueError, match="Unsupported image type"):
        image_to_data_url(path)
