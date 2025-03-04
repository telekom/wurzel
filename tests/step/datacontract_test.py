# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import pytest
import wurzel.datacontract as dac
from pandera.typing import Series, DataFrame
from pathlib import Path
class MyCSV(dac. PanderaDataFrameModel):
    col0: Series[int]
def test_dvc_store_load(tmp_path,):
    expected = [1,2,3,4,5,7]
    path = tmp_path/f"output"
    x = DataFrame[MyCSV]({"col0": expected})
    save_path = MyCSV.save_to_path(path, x)
    assert save_path.suffix == ".csv"
    loaded = MyCSV.load_from_path(save_path)
    assert list(loaded.col0) == expected

def test_dvc_load_wrong_encoding():
    with pytest.raises(FileNotFoundError):
        MyCSV.load_from_path(Path("/tmp/not_a_file.no-encoding"))