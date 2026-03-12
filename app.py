import os
import io
import base64
import cv2
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from datetime import datetime
from flask import Flask, request, jsonify, render_template, send_from_directory
from database import db, CDR as cd_ratio_table
from inference import load_models, measure_cd_ratio

app = Flask(__name__)

app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///cd_ratio.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024

db.init_app(app)

with app.app_context():
    db.create_all()

disc_model, cup_model = load_models(
    os.environ.get("DISC_MODEL_PATH", "models/disc_model.keras"),
    os.environ.get("CUP_MODEL_PATH",  "models/cup_model.keras"),
)




@app.route("/demo_images/<filename>")
def demo_image(filename):
    demo_dir = os.path.join(os.path.dirname(__file__), "demo_images")
    return send_from_directory(demo_dir, filename, as_attachment=True)




@app.route("/")
def index():
    return render_template("index.html")




@app.route("/measure", methods=["POST"])
def measure():
    if "image" not in request.files:
        return jsonify({"error": "No image provided"}), 400

    px_id = request.form.get("patient_id", "").strip()
    if not px_id:
        return jsonify({"error": "patient_id is required"}), 400

    eye = request.form.get("eye", "right").strip().lower()
    if eye not in ("right", "left"):
        return jsonify({"error": "eye must be 'right' or 'left'"}), 400

    try:
        year = int(request.form.get("year", datetime.utcnow().year))
    except ValueError:
        return jsonify({"error": "year must be a number"}), 400

    file_bytes = np.frombuffer(request.files["image"].read(), np.uint8)
    image_bgr  = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
    if image_bgr is None:
        return jsonify({"error": "Could not decode image — ensure it is JPEG or PNG"}), 422

    image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)

    try:
        result = measure_cd_ratio(image_rgb, disc_model, cup_model)
    except ValueError as e:
        return jsonify({"error": str(e)}), 422

    # Build overlay mask image and encode as base64
    mask_b64 = _build_mask_overlay(image_rgb, result["disc_mask"], result["cup_mask"])

    record = cd_ratio_table(
        px_id=px_id,
        eye=eye,
        year=year,
        cd_ratio=result["cd_ratio"],
        disc_area=result["disc_area"],
        cup_area=result["cup_area"],
    )
    db.session.add(record)
    db.session.commit()

    return jsonify({
        "id":       record.id,
        "px_id":    px_id,
        "eye":      eye,
        "year":     year,
        "cd_ratio": result["cd_ratio"],
        "disc_area":result["disc_area"],
        "cup_area": result["cup_area"],
        "mask_b64": mask_b64,
    }), 201


def _build_mask_overlay(image_rgb, disc_mask, cup_mask):
    """Render coloured mask overlaid on fundus image, return base64 PNG."""
    overlay = image_rgb.copy().astype(np.float32)
    # Disc — semi-transparent green
    disc_layer = np.zeros_like(overlay)
    disc_layer[disc_mask == 1] = [0, 255, 100]
    overlay = cv2.addWeighted(overlay, 1.0, disc_layer, 0.35, 0)
    # Cup — semi-transparent purple
    cup_layer = np.zeros_like(overlay)
    cup_layer[cup_mask == 1] = [255, 110, 60]
    overlay = cv2.addWeighted(overlay, 1.0, cup_layer, 0.45, 0)
    overlay = np.clip(overlay, 0, 255).astype(np.uint8)
    _, buf = cv2.imencode(".png", cv2.cvtColor(overlay, cv2.COLOR_RGB2BGR))
    return base64.b64encode(buf).decode()




@app.route("/measure/<int:record_id>/mask", methods=["GET"])
def get_mask(record_id):
    #fallback if mask fail
    return jsonify({"error": "Mask is returned inline in POST /measure"}), 404




@app.route("/measure/<px_id>", methods=["GET"])
def return_by_id(px_id):
    results = cd_ratio_table.query.filter_by(px_id=px_id).all()
    if not results:
        return jsonify({"error": "Patient ID does not exist"}), 404
    return jsonify([r.to_dict() for r in results])


@app.route("/measure/<px_id>", methods=["DELETE"])
def delete_record(px_id):
    results = cd_ratio_table.query.filter_by(px_id=px_id).all()
    if not results:
        return jsonify({"error": "Patient ID does not exist"}), 404
    for record in results:
        db.session.delete(record)
    db.session.commit()
    return jsonify({"message": f"All records for {px_id} deleted"}), 200


@app.route("/measure/<int:record_id>", methods=["PUT"])
def update_record(record_id):
    record = cd_ratio_table.query.get(record_id)
    if not record:
        return jsonify({"error": "Record not found"}), 404
    data = request.get_json()
    if "year" in data:
        record.year = data["year"]
    if "patient_id" in data:
        record.px_id = data["patient_id"]
    if "eye" in data:
        record.eye = data["eye"]
    db.session.commit()
    return jsonify(record.to_dict()), 200



@app.route("/patients/<px_id>", methods=["GET"])
def get_patient(px_id):
    eye = request.args.get("eye", None)
    q   = cd_ratio_table.query.filter_by(px_id=px_id)
    if eye:
        q = q.filter_by(eye=eye)
    results = q.order_by(cd_ratio_table.year).all()
    if not results:
        return jsonify({"error": "Patient not found"}), 404
    return jsonify([r.to_dict() for r in results]), 200


@app.route("/patients/<px_id>/trend", methods=["GET"])
def get_trend(px_id):
    eye = request.args.get("eye", None)
    q   = cd_ratio_table.query.filter_by(px_id=px_id)
    if eye:
        q = q.filter_by(eye=eye)
    results = q.order_by(cd_ratio_table.year).all()

    if not results:
        return jsonify({"error": "Patient not found"}), 404
    if len(results) < 2:
        return jsonify({"error": "Need at least 2 records to plot a trend"}), 400

    years  = [r.year     for r in results]
    ratios = [r.cd_ratio for r in results]

    # ── Styled chart ──────────────────────────────────────────────────────────
    BG      = "#050508"
    SURFACE = "#0d0d14"
    PURPLE  = "#ff6e3c"
    WHITE   = "#e8e8f0"
    MUTED   = "#6b6b80"

    fig, ax = plt.subplots(figsize=(8, 3.5))
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(SURFACE)

    # Gridlines — white at 50% opacity
    ax.yaxis.set_major_locator(ticker.MultipleLocator(0.1))
    ax.grid(axis='y', color='white', alpha=0.5, linewidth=0.6, linestyle='--')
    ax.grid(axis='x', color='white', alpha=0.2, linewidth=0.4, linestyle=':')
    ax.set_axisbelow(True)

    # Plot — black dots & line
    ax.plot(years, ratios,
            color='#000000', linewidth=1.8, zorder=3,
            marker='o', markersize=7,
            markerfacecolor='#000000', markeredgecolor=PURPLE, markeredgewidth=1.5)


    ax.fill_between(years, ratios, alpha=0.08, color=PURPLE, zorder=2)


    ax.axhline(0.6, color=PURPLE, linewidth=0.8, linestyle='--', alpha=0.5, zorder=4)
    ax.text(years[-1], 0.61, 'threshold', color=PURPLE, fontsize=8, alpha=0.7, ha='right')


    ax.set_xlabel("Year",    color=MUTED, fontsize=10, labelpad=8)
    ax.set_ylabel("C/D Ratio", color=MUTED, fontsize=10, labelpad=8)
    ax.set_ylim(0, 1)
    ax.set_xlim(min(years) - 0.3, max(years) + 0.3)
    ax.xaxis.set_major_locator(ticker.MaxNLocator(integer=True))


    ax.tick_params(colors=WHITE, labelsize=9)
    for spine in ax.spines.values():
        spine.set_edgecolor(MUTED)
        spine.set_alpha(0.4)

    eye_label = (eye or 'both').capitalize()
    ax.set_title(f"C/D Ratio — {px_id} ({eye_label} Eye)",
                 color=WHITE, fontsize=11, pad=12, fontweight='bold')

    fig.tight_layout(pad=1.2)

    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=140, facecolor=BG)
    plt.close(fig)
    buf.seek(0)

    return jsonify({"chart": base64.b64encode(buf.read()).decode()}), 200


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)