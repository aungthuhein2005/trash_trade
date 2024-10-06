import cv2
import numpy as np
from tensorflow.keras.models import load_model

# Load the model
model = load_model('D:/projects/data_train/waste_detection_model.h5')

# Function to predict image class
def predict_image(image_path):
    img = cv2.imread(image_path)
    img = cv2.resize(img, (128, 128))
    img = np.expand_dims(img, axis=0)  # Add batch dimension
    img = img / 255.0  # Normalize the image
    prediction = model.predict(img)
    return np.argmax(prediction)

# Example usage:
predicted_class = predict_image('metal6.jpg')
print(f'Predicted class: {predicted_class}')
