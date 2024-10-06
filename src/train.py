import numpy as np
from sklearn.model_selection import train_test_split
from load_data import load_data
from model import create_model

# Load data
X, y = load_data('D:/projects/data_train/dataset')

# Get image dimensions
image_height, image_width, num_channels = X.shape[1], X.shape[2], X.shape[3]

# Split into training and validation sets
X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.2, random_state=42)

# Normalize the images
X_train = X_train / 255.0
X_val = X_val / 255.0

# Create model
model = create_model(image_height, image_width, num_channels)

# Train model
model.fit(X_train, y_train, epochs=10, validation_data=(X_val, y_val))

# Save model
model.save('D:/projects/data_train/waste_detection_model.h5')
