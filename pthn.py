import numpy as np
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense
from tensorflow.keras.optimizers import Adam
from sklearn.model_selection import train_test_split

data = np.array([
    [0.85, 25],
    [0.78, 34],
    [0.90, 22],
    [0.50, 29],
    [0.65, 45],
    [0.95, 19],
])

labels = np.array([1, 1, 1, 0, 0, 1])

X_train, X_test, y_train, y_test = train_test_split(data, labels, test_size=0.2, random_state=42)

model = Sequential([
    Dense(16, input_shape=(2,), activation='relu'),
    Dense(8, activation='relu'),
    Dense(1, activation='sigmoid')
])

model.compile(optimizer=Adam(learning_rate=0.001), loss='binary_crossentropy', metrics=['accuracy'])

epochs = 50
for epoch in range(epochs):
    model.fit(X_train, y_train, epochs=1, batch_size=2, validation_split=0.1, verbose=0)
    predictions = model.predict(X_train).flatten()
    for i in range(len(predictions)):
        if (predictions[i] >= 0.5 and y_train[i] == 0) or (predictions[i] < 0.5 and y_train[i] == 1):
            weights = model.get_weights()
            updated_weights = [w * 1.05 for w in weights]
            model.set_weights(updated_weights)

loss, accuracy = model.evaluate(X_test, y_test)
print(f"Точность модели на тестовых данных: {accuracy * 100:.2f}%")

test_predictions = model.predict(X_test)

for i, prediction in enumerate(test_predictions):
    binary_prediction = 1 if prediction[0] >= 0.5 else 0
    result_text = "Пройдёт" if binary_prediction == 1 else "Не пройдёт"
    print(f"Пользователь {i+1}: Вероятность прохождения - {prediction[0]:.2f}, Предсказание - {result_text}, Фактический результат - {y_test[i]}")

def predict_survey_eligibility(model, compatibility, age):
    new_data = np.array([[compatibility, age]])
    probability = model.predict(new_data)[0][0]
    prediction = 1 if probability >= 0.5 else 0
    result_text = "Пройдёт" if prediction == 1 else "Не пройдёт"
    print(f"Вероятность прохождения: {probability:.2f}, Предсказание - {result_text}")
    return prediction

predict_survey_eligibility(model, 0.76, 30)
