from keras import layers, models

def create_model(image_height, image_width, num_channels):
    model = models.Sequential([
        layers.Conv2D(32, (3, 3), activation='relu', input_shape=(image_height, image_width, num_channels)),
        layers.MaxPooling2D((2, 2)),
        layers.Conv2D(64, (3, 3), activation='relu'),
        layers.MaxPooling2D((2, 2)),
        layers.Flatten(),
        layers.Dense(64, activation='relu'),
        layers.Dense(6, activation='softmax')
    ])
    model.compile(optimizer='adam', loss='sparse_categorical_crossentropy', metrics=['accuracy'])
    return model
