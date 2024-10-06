import cv2
import numpy as np

def predict_image(image_path, model):
    img = cv2.imread(image_path)
    img = cv2.resize(img, (128, 128))
    img = np.expand_dims(img, axis=0)  # Add batch dimension
    img = img / 255.0  # Normalize the image
    prediction = model.predict(img)
    return np.argmax(prediction)
