# OCDR — Optic Cup-to-Disc Ratio Monitor 🔬

> Early Demo (BETA) [work in progress]

Automated tool for monitoring optic cup-to-disc ratio (CDR) changes over time, removing subjective unreliablity between professionals.

---

## Model

Built on the [DRISHTI-GS dataset](https://www.kaggle.com/datasets/lokeshsaipureddi/drishtigs-retina-dataset-for-onh-segmentation) 

The optic disc and optic cup were trained as **two separate segmentation models** using an EfficientNetB4 U-Net architecture, allowing independent mask prediction before CDR is calculated from vertical diameter ratio. 

---

## Stack

- **Backend** — Flask REST API
- **ML** — Keras / TensorFlow (EfficientNetB4 U-Net)
- **Frontend** — Jinja2 + Alpine.js
- **Database** — SQLAlchemy / SQLite (PostgreSQL-ready)

Everything is in the `backend/` folde for demo purposes.

---

## Current Limitations

- Optimised for **centralised ONH fundus photos only** (Standard fundography images off-centre or will produce unreliable results)
- Models require further training and validation across diverse image types and noise management
- Demo dataset is limited — not yet validated for clinical use

---

## Roadmap

- [ ] AWS deployment with image storage (S3 + RDS)
- [ ] Secure 2FA login
- [ ] Support for peripheral and wide-field fundus images
- [ ] Extended model training across broader datasets

---

## Disclaimer

This is a research/portfolio project. Not validated for clinical decision-making.
