from tensorflow.keras.models import load_model
from load_data import load_data
from sklearn.model_selection import train_test_split

# Load data
X, y = load_data('D:/projects/data_train/dataset')

# Split data into training and validation sets
_, X_val, _, y_val = train_test_split(X, y, test_size=0.2, random_state=42)

# Normalize the images
X_val = X_val / 255.0

# Load the saved model
model = load_model('D:/projects/data_train/waste_detection_model.h5')

# Evaluate the model
val_loss, val_acc = model.evaluate(X_val, y_val)
print(f'Validation accuracy: {val_acc}')
