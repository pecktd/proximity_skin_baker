# Proximity Skin Baker

A tool for baking deformations into skin weights in Autodesk Maya.

---

## 🧩 Overview

`Proximity Skin Baker` simplifies the process of transferring complex deformations to skin weights — especially in cases where traditional baking tools fall short due to joint-controller constraints or lack of direct access to skin joints.

While Maya's native Bake Deformations tool is powerful, it's not always rigger-friendly. This tool works around common limitations by rebuilding the necessary hierarchy and using a proximity-based approach to match deformations before baking.

---

## ⚙️ How It Works

The process is divided into **two main phases**:

### 🔧 Phase 1: Setup
- Duplicates:
  - Source geometry (skinned)
  - Target geometry
  - Skinning joint hierarchy (cleaned)
- Applies a **Proximity Wrap** from the duplicated source to the duplicated target.
- Optional: Add a **Delta Mush** deformer or tweak proximity falloff for better results.

This allows riggers to inspect, adjust, and preview deformation quality before committing to bake.

---

### 🔥 Phase 2: Bake
- Transfers the deformation from the wrapped geometry directly into the **skin cluster** on the target geometry.
- Final result: Clean skin weights that replicate the deformation without needing the original deformers.

---

## ⚠️ Limitations

- Only supports **a single joint chain** for skinning in the current version.
- Multi-chain or branching joint hierarchies are **not yet supported** (but planned for a future release).

