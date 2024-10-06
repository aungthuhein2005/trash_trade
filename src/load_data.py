import os
import cv2
import numpy as np

def load_data(data_dir):
    images = []
    labels = []
    label_dict = {'plastic': 0, 'paper': 1, 'glass': 2, 'metal': 3, 'cardboard': 4, 'trash': 5}

    for label in label_dict:
        folder_path = os.path.join(data_dir, label)
        for filename in os.listdir(folder_path):
            img_path = os.path.join(folder_path, filename)
            img = cv2.imread(img_path)
            img = cv2.resize(img, (128, 128))  # Resize to 128x128
            images.append(img)
            labels.append(label_dict[label])

    return np.array(images), np.array(labels)

# Example usage:
# X_train, y_train = load_data('../dataset')
