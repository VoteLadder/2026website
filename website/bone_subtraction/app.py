import os
from flask import Flask, render_template, request, send_file
import torch
from torchvision import transforms
from PIL import Image
import io
from model import UNetGenerator  # Assuming UNetGenerator is defined in model.py

# Define the Flask app with custom template folder
app = Flask(__name__, template_folder='/var/www/html/website/bone_subtraction/templates')

# Define absolute paths for uploads and outputs
app.config['UPLOAD_FOLDER'] = '/var/www/html/website/bone_subtraction/uploads'
app.config['OUTPUT_FOLDER'] = '/var/www/html/website/bone_subtraction/outputs'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)

# Load model once when the app starts
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model_path = '/var/www/html/website/bone_subtraction/9_14_best_final.pth'  # Absolute path to the weights file
model = UNetGenerator().to(device)
model.load_state_dict(torch.load(model_path, map_location=device))
model.eval()

# Helper functions for image loading and saving
def load_and_preprocess_image(image_path):
    image = Image.open(image_path).convert('L')  # Convert to grayscale
    transform = transforms.Compose([
        transforms.Resize((256, 256)),
        transforms.ToTensor(),
    ])
    return transform(image).unsqueeze(0)

def save_output(output):
    # Convert the output tensor to a PIL Image
    output_image = transforms.ToPILImage()(output.squeeze().cpu())
    
    # Save to BytesIO object
    img_byte_arr = io.BytesIO()
    output_image.save(img_byte_arr, format='PNG')
    img_byte_arr.seek(0)
    
    return img_byte_arr

# Define the route
@app.route('/bone_subtraction/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        if 'file' not in request.files:
            return 'No file part', 400
        file = request.files['file']
        if file.filename == '':
            return 'No selected file', 400
        if file:
            try:
                # Save uploaded file
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
                file.save(file_path)
                print(f"File saved at: {file_path}")
                
                # Process the image
                input_image = load_and_preprocess_image(file_path).to(device)
                print(f"Input image processed, shape: {input_image.shape}, device: {input_image.device}")

                with torch.no_grad():
                    output = model(input_image)
                print("Model processing completed successfully")

                # Save and return the processed image
                output_bytes = save_output(output)
                return send_file(output_bytes, mimetype='image/png')

            except Exception as e:
                # Print the error details to the console for debugging
                error_message = f"Error during processing: {str(e)}"
                print(error_message)
                return error_message, 500

    return render_template('index.html')

# Run the Flask app
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

