# HelloBeauty 🪞

> **JESR 人像精修平台** — Joint Evaluation Scoring & Rendering for Automated Portrait Retouch  
> 设计和实现一款基于 AIGC 技术的智能化照片美颜精修系统

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![TypeScript](https://img.shields.io/badge/typescript-5.x-blue.svg)](https://www.typescriptlang.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688.svg)](https://fastapi.tiangolo.com/)

**HelloBeauty** is an AIGC-powered portrait retouch platform that replaces traditional filter-based workflows with a **perception → decision → execution pipeline**. It introduces the **JESR-Aesthetic-Profile** — an 8-dimensional feature vector that bridges user intent to rendering parameters — and a **metric-controlled guard** that ensures identity preservation during generative edits.

---

## 系统架构 · System Architecture

![System Architecture](docs/images/architecture.svg)

The pipeline has five layers:

| 层 Layer | 模块 Module | 职责 Responsibility |
|:---|:---|:---|
| **Entry** 入口 | Phone Upload · Seed Gallery · Preference QA | User intent capture via swipe, questionnaire, or reference photos |
| **JESR-Core** 核心 | JESR-Aesthetic-Profile · Recipe System | 8-dim profile vector → parameterized recipe in 3 domains (tone, face, creative) |
| **Orchestrator** 编排 | Recipe Compilation · Feedback · Rollback · Audit | Stateful SISO loop: iterate → feedback → update → re-render |
| **Rendering** 渲染 | JESR-Fidelity · JESR-Creative · Metric Control | Smart optimize + targeted retouch → diffusion img2img → identity guard |
| **Output** 输出 | Image Delivery · Session Persistence · Logging | Rendered result via `/api/assets/job/{id}` |

### JESR-Aesthetic-Profile Vector

The profile encodes user aesthetic preferences in 8 continuous dimensions (range [-1, 1]):

| Dimension | Description |
|:---|:---|
| `light_tendency` | Preference for bright vs. dark tone |
| `warmth` | Warm vs. cool color temperature |
| `contrast` | High vs. low contrast |
| `texture_tendency` | Preference for skin texture preservation |
| `makeup_intensity` | Makeup strength (lip color, eye emphasis) |
| `facial_detail_preference` | How much facial reshaping is acceptable |
| `style_strength` | Creative style transfer intensity |
| `identity_tolerance` | Acceptable identity drift (governs metric control threshold) |

### Metric Control Guard

Before delivering creative (diffusion img2img) output, the system evaluates identity similarity (ArcFace / FaceNet). If similarity falls below threshold, it retries with progressively reduced denoising strength (4 steps, floor 0.08). On all failures, it falls back to the fidelity output — ensuring **identity is never compromised for style**.

---

## 仓库结构 · Repository Structure

```
HelloBeauty/
├── backend/
│   ├── api/              # FastAPI routes (sessions, photos, recipes, render, models, assets)
│   ├── jesr/             # JESR-Orchestrator, Metric Control, Feedback, Recipe Trace
│   ├── providers/        # JESR-Fidelity / JESR-Creative provider interfaces
│   ├── services/         # Session store, storage, ingress (photo upload)
│   └── app.py            # FastAPI application entry point
├── packages/
│   ├── jesr_core/        # Python: JESR-Aesthetic-Profile engine & recipe system
│   ├── domain/           # TypeScript: shared domain types (JESR interfaces, metrics)
│   ├── api-client/       # TypeScript: transport-agnostic API client
│   └── design-tokens/    # Shared design tokens
├── apps/
│   ├── mini/src/         # Taro mini-app (swipe UI, retouch pages, API utils)
│   └── web/app/          # Next.js marketing/landing page
├── tests/                # pytest + API contract tests
├── docs/images/          # Architecture diagram
├── scripts/              # Startup script
└── pyproject.toml / package.json / tsconfig.base.json
```

---

## 核心亮点 · Key Innovations

### 1. Profile-Driven Recipe Compilation
User preferences (from swipe sampling or questionnaire) are not treated as direct sliders. Instead, the 8-dim profile vector maps through **8 linear algebraic transforms** into tone, face, and creative parameters — ensuring cross-dimensional consistency.

### 2. SISO Feedback Loop with Rollback
Each render produces an audit trace. The feedback interpreter maps both structured pain tags and free-text input to recipe deltas. Every iteration is versioned — the rollback API can restore any prior state.

### 3. Identity-Guarded Diffusion
The metric control loop evaluates identity similarity (≥θ threshold) before accepting creative output. When identity degrades, it retries with reduced strength (4-step descent) and falls back to fidelity on guard failure.

### 4. Model Distribution: Code in Git, Weights via Release
Model manifests and adapter code live in the repository. Model weights (GPEN, SSD-1B) are distributed as GitHub Release assets, mounted at runtime — **no large binary files in Git history**.

---

## 技术栈 · Tech Stack

| Layer | Technology |
|:---|:---|
| Backend API | Python 3.10+ · FastAPI · Uvicorn |
| JESR-Core | Python (pure NumPy-free profile engine) |
| Rendering | GPEN BFR512 (face restoration) · SSD-1B diffusers (style transfer) |
| Identity Metric | ArcFace · FaceNet |
| Frontend Mini | TypeScript · Taro 3.x · React |
| Frontend Web | Next.js · React |
| Packages | TypeScript monorepo (shared domain types) |

---

## 快速开始 · Quick Start

### Prerequisites
- Python 3.10+ with `pip`
- Node.js 20+
- Model weights downloaded as GitHub Release assets

### Start Backend
```bash
# Install Python deps
pip install -e packages/jesr_core
pip install fastapi uvicorn pillow

# Start API server
bash scripts/start_backend.sh
# → API: http://127.0.0.1:7860/docs
# → Health: http://127.0.0.1:7860/api/health
```

### Run Tests
```bash
python -m pytest tests -q
```

### Frontend (Mini App)
```bash
npm install
npm run build:mini
```

---

## 注意事项 · Important Notes

### ⚠️ 此仓库包含什么 · What's Included
- ✅ 完整 API 路由层 (full API surface — all routes & contracts)
- ✅ JESR 编排器与度量控制核心算法 (orchestrator + metric control algorithm)
- ✅ JESR-Aesthetic-Profile 引擎 (8-dim profile vector with mathematical transforms)
- ✅ TypeScript 领域类型定义 (shared domain types & API client interfaces)
- ✅ 前端关键页面组件 (key frontend pages for architecture reference)
- ✅ 测试文件 (tests demonstrating API contracts)
- ✅ 系统架构图 (architecture diagram)

### ⚠️ 此仓库不包含什么 · What's NOT Included
- ❌ **模型权重 (Model Weights)** — GPEN BFR512, SSD-1B, ArcFace models distributed via GitHub Releases
- ❌ **模型适配器实现 (Model Adapters)** — `backend/model_adapters/` 包含特定模型的命令路径
- ❌ **模型清单/注册表 (Model Registry)** — `backend/models/` 包含版本哈希与模型元数据
- ❌ **渲染工作进程 (Render Worker)** — `backend/workers/` 后台渲染逻辑
- ❌ **实验脚本 (Experiment Scripts)** — `scripts/run_real_metric_experiments.py`（117 KB 实验脚本）
- ❌ **供应商库 (Vendor Libraries)** — `vendor/` 及 `npm/` 目录
- ❌ **图片资源库 (Beauty Gallery)** — `beauty/` 示例人像照片
- ❌ **完整前端项目文件 (Complete IDE Project)** — 仅包含代表性页面，非完整可构建项目

> **设计意图：** 此仓库展示系统架构、核心算法与 API 契约，足够理解 JESR 系统设计但无法直接克隆运行。模型权重与完整项目文件通过其他渠道分发。

---

## 许可证 · License

Apache 2.0 © 2024 HelloBeauty Contributors. See [LICENSE](LICENSE).

---

## 致谢 · Acknowledgements

本项目源于本科毕业设计《基于 AIGC 技术的智能化照片美颜精修系统的设计与实现》。

> "如何在维持身份一致性前提下，对五官比例、肤质细节、妆容风格及光影关系进行可控、自然的联合编辑；如何依据用户隐式或极少显式偏好生成非模板化的个性化结果。" — 研究意义

JESR stands for **Joint Evaluation Scoring & Rendering** — evaluating aesthetic quality and identity preservation jointly during the rendering decision process.
