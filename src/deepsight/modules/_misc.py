# Copyright 2024 The DeepSight Team.
# SPDX-License-Identifier: Apache-2.0
# --------------------------------------------------------------------------- #
# Copyright 2020 Ross Wightman
# SPDX-License-Identifier: Apache-2.0
# --------------------------------------------------------------------------- #
# Modified from:
# https://github.com/huggingface/pytorch-image-models/blob/main/timm/models/vision_transformer.py
# --------------------------------------------------------------------------- #

from typing import Literal

import torch
from torch import nn

from deepsight.typing import Tensor

from ._module import Module


class LayerScale(Module):
    def __init__(
        self,
        dim: int,
        init_value: float = 1e-5,
        inplace: bool = False,
    ) -> None:
        super().__init__()

        self.inplace = inplace
        self.gamma = nn.Parameter(torch.full((dim,), init_value))

    def __call__(
        self, x: Tensor[Literal["..."], float]
    ) -> Tensor[Literal["..."], float]:
        return x.mul_(self.gamma) if self.inplace else x * self.gamma
