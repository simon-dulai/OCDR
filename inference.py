import numpy as np
import cv2
import keras
from keras.applications.efficientnet import  preprocess_input

def load_models(disc_path, cup_path):
    disc_model = keras.models.load_model(disc_path, compile=False)
    cup_model = keras.models.load_model(cup_path, compile=False)
    return disc_model, cup_model

def measure_cd_ratio(image_array, disc_model, cup_model):
    og_h, og_w = image_array.shape[:2]

    img_512 = cv2.resize(image_array, (512,512)).astype(np.float32)
    img_pre = preprocess_input(img_512)
    batch = np.expand_dims(img_pre, axis = 0)

    predicted_disc = disc_model.predict(batch, verbose = 0)[0, :,:,0]
    predicted_cup = cup_model.predict(batch, verbose=0)[0, :, :, 0]

    #tweak if cup isnt being marked properly
    disc_mask_512 = ( predicted_disc > 0.5).astype(np.uint8)
    cup_mask_512 = (predicted_cup > 0.5).astype(np.uint8)
    # Resize masks back to original resolution - avoids any blending
    disc_mask = cv2.resize(disc_mask_512, (og_w, og_h), interpolation=cv2.INTER_NEAREST)
    cup_mask = cv2.resize(cup_mask_512, (og_w, og_h), interpolation=cv2.INTER_NEAREST)
    cd_ratio = calc_cd_ratio(disc_mask, cup_mask)
    disc_area = float(np.sum(disc_mask))
    cup_area = float(np.sum(cup_mask))

    return {
        "disc_mask": disc_mask,
        "cup_mask": cup_mask,
        "cd_ratio": cd_ratio,
        "disc_area": disc_area,
        "cup_area": cup_area,
    }

def calc_cd_ratio(disc_mask, cup_mask):

    disc_diam = v_diameter(disc_mask)
    cup_diam  = v_diameter(cup_mask)

    if disc_diam and disc_diam > 0 and cup_diam is not None:
        return round(float(cup_diam) / float(disc_diam), 4)

    if disc_diam is None or disc_diam == 0:
        raise ValueError("Could not detect optic disc accurately — please retake image")
    return 0.0

def v_diameter(mask):
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        raise ValueError("No disc/cup detected — image quality too low")
    largest = max(contours, key=cv2.contourArea)
    if len(largest) < 5:
        raise ValueError("Mask too small to fit ellipse — image quality too low")

    _, (MA, ma), _ = cv2.fitEllipse(largest)
    return min(MA, ma)  # minor axis = vertical diameter
