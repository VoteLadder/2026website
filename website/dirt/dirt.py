import sys
import os
import numpy as np
import pydicom
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QGraphicsView, QGraphicsScene, QGraphicsPixmapItem,
    QGraphicsEllipseItem, QVBoxLayout, QWidget, QLabel, QSlider,
    QHBoxLayout, QCheckBox, QLineEdit, QTableWidget, QTableWidgetItem, QFileDialog,
    QSizePolicy, QComboBox, QMessageBox, QSplitter, QPushButton
)
from PyQt5.QtCore import Qt, QRectF, QPointF
from PyQt5.QtGui import QPixmap, QImage, QPen


class DICOMViewer(QMainWindow):
    def __init__(self):
        super().__init__()

        # Initialize attributes
        self.dicom_path = None
        self.images = None
        self.slices = []
        self.current_slice = 0
        self.rois = []  # Store ROI information
        self.roi_data = {}  # Store data of each ROI for plotting
        self.pixmap_item = None
        self.roi_item = None
        self.roi_diameter = 50  # Default ROI diameter

        # Prompt user to select DICOM path
        self.dicom_path = self.select_dicom_path()

        if not self.dicom_path:
            QMessageBox.critical(self, "No Selection", "No DICOM file or directory selected. Exiting application.")
            sys.exit(1)  # Exit if no file or directory is selected

        # Load initial DICOM images
        try:
            self.load_images()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load DICOM images: {e}")
            sys.exit(1)

        # Initialize UI
        self.initUI()

    def select_dicom_path(self):
        """Prompt the user to select a DICOM directory or file."""
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog

        # Default to showing all files first, rather than only DICOM files
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select DICOM File or Directory", "", "All Files (*);;DICOM Files (*.dcm)", options=options
        )

        if file_path:
            return file_path

        # If no file is selected, prompt to select a directory
        directory = QFileDialog.getExistingDirectory(
            self, "Select DICOM Directory", "", options=QFileDialog.ShowDirsOnly
        )
        return directory if directory else None

    def load_images(self):
        """Load images based on the selected dicom_path."""
        if os.path.isfile(self.dicom_path):
            self.images, self.slices = self.load_single_dicom(self.dicom_path)
        else:
            self.images, self.slices = self.load_dicom_series(self.dicom_path)
        self.current_slice = 0
        self.rois = []
        print("Images loaded successfully.")

    def load_single_dicom(self, filepath):
        """Load a single DICOM file."""
        try:
            ds = pydicom.dcmread(filepath)
            if hasattr(ds, 'pixel_array'):
                frames = ds.pixel_array
                images_list = []
                if frames.ndim == 3:
                    images_list.extend(frames)
                elif frames.ndim == 2:
                    images_list.append(frames)
                else:
                    raise ValueError(f"Unsupported pixel_array shape: {frames.shape}")
                images_np = np.stack(images_list, axis=0)
                images = images_np.astype(np.float32)
                print(f"Loaded {images.shape[0]} image slice(s) from the single DICOM file with shape {images.shape[1:]} each.")
                return images, [ds]
            else:
                QMessageBox.critical(self, "Error", "No pixel data found in the selected DICOM file.")
                raise ValueError("No pixel data found in the specified DICOM file.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load DICOM file: {e}")
            raise

    def load_dicom_series(self, directory):
        """Load a series of DICOM files from the directory."""
        slices = []
        for filename in os.listdir(directory):
            if filename.endswith('.dcm') or filename == 'XA_00001':
                filepath = os.path.join(directory, filename)
                try:
                    ds = pydicom.dcmread(filepath)
                    slices.append(ds)
                except Exception as e:
                    print(f"Failed to read {filepath}: {e}")

        if not slices:
            QMessageBox.critical(self, "Error", "No DICOM files found in the selected directory.")
            raise ValueError("No DICOM files found in the specified directory.")

        try:
            slices.sort(key=lambda x: int(x.InstanceNumber))
            print("DICOM slices sorted by InstanceNumber.")
        except AttributeError:
            slices.sort(key=lambda x: x.SOPInstanceUID)
            print("DICOM slices sorted by SOPInstanceUID.")

        images_list = []
        for s in slices:
            frames = s.pixel_array
            if frames.ndim == 3:
                images_list.extend(frames)
            elif frames.ndim == 2:
                images_list.append(frames)
            else:
                raise ValueError(f"Unsupported pixel_array shape: {frames.shape}")

        images_np = np.stack(images_list, axis=0)
        images = images_np.astype(np.float32)
        print(f"Loaded {images.shape[0]} image slices from the directory with shape {images.shape[1:]} each.")
        return images, slices

    def initUI(self):
        """Initialize the user interface."""
        self.setWindowTitle('Dicom Image Region Trender (DIRT) - by Emil Cohen')
        self.setGeometry(100, 100, 1920, 1080)
        self.setMinimumSize(1600, 900)
        self.showMaximized()

        # Main Widget and Layout using QSplitter for resizable panes
        self.main_widget = QWidget(self)
        self.setCentralWidget(self.main_widget)
        main_layout = QHBoxLayout(self.main_widget)

        splitter = QSplitter(Qt.Horizontal)

        # Left Widget for Image
        self.image_widget = QWidget()
        self.image_layout = QVBoxLayout(self.image_widget)
        self.graphics_view = QGraphicsView(self)
        self.graphics_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.scene = QGraphicsScene()
        self.graphics_view.setScene(self.scene)
        self.image_layout.addWidget(self.graphics_view)
        splitter.addWidget(self.image_widget)

        # Right Widget for Controls
        self.controls_widget = QWidget()
        self.controls_layout = QVBoxLayout(self.controls_widget)

        # Slice Slider
        self.slice_slider = QSlider(Qt.Horizontal)
        self.slice_slider.setMinimum(0)
        self.slice_slider.setMaximum(self.images.shape[0] - 1)
        self.slice_slider.setValue(0)
        self.slice_slider.setTickInterval(1)
        self.slice_slider.valueChanged.connect(self.update_slice)
        self.controls_layout.addWidget(QLabel('Slice:'))
        self.controls_layout.addWidget(self.slice_slider)

        # Window Slider
        self.window_slider = QSlider(Qt.Horizontal)
        self.window_slider.setMinimum(1)
        self.window_slider.setMaximum(4096)
        self.window_slider.setValue(128)
        self.window_slider.setTickInterval(1)
        self.window_slider.valueChanged.connect(self.update_window_level)
        self.controls_layout.addWidget(QLabel('Window Width:'))
        self.controls_layout.addWidget(self.window_slider)

        # Level Slider
        self.level_slider = QSlider(Qt.Horizontal)
        self.level_slider.setMinimum(-4096)
        self.level_slider.setMaximum(4096)
        self.level_slider.setValue(128)
        self.level_slider.setTickInterval(1)
        self.level_slider.valueChanged.connect(self.update_window_level)
        self.controls_layout.addWidget(QLabel('Window Level:'))
        self.controls_layout.addWidget(self.level_slider)

        # Auto Window Button
        self.auto_window_button = QPushButton("Auto Window")
        self.auto_window_button.clicked.connect(self.auto_window)
        self.controls_layout.addWidget(self.auto_window_button)

        # Diameter Slider
        self.diameter_slider = QSlider(Qt.Horizontal)
        self.diameter_slider.setMinimum(1)
        self.diameter_slider.setMaximum(200)
        self.diameter_slider.setValue(self.roi_diameter)
        self.diameter_slider.setTickInterval(1)
        self.diameter_slider.valueChanged.connect(self.update_roi_diameter)
        self.controls_layout.addWidget(QLabel('ROI Diameter (px):'))
        self.controls_layout.addWidget(self.diameter_slider)

        # Subtraction Option
        self.subtraction_combo = QComboBox(self)
        self.subtraction_combo.addItem('None')
        for i in range(self.images.shape[0]):
            self.subtraction_combo.addItem(f'Image {i}')
        self.subtraction_combo.currentIndexChanged.connect(self.display_slice)
        self.controls_layout.addWidget(QLabel('Subtraction Image:'))
        self.controls_layout.addWidget(self.subtraction_combo)

        # Overlay Toggle
        self.overlay_checkbox = QCheckBox('Show ROI Overlay')
        self.overlay_checkbox.setChecked(True)
        self.overlay_checkbox.stateChanged.connect(self.display_slice)
        self.controls_layout.addWidget(self.overlay_checkbox)

        # Status Label
        self.status_label = QLabel(f"Slice: {self.current_slice}", self)
        self.controls_layout.addWidget(self.status_label)

        # ROI Analysis and Save Button
        roi_controls = QHBoxLayout()
        self.analyze_roi_button = QPushButton('Analyze ROI')
        self.analyze_roi_button.clicked.connect(self.analyze_roi)
        roi_controls.addWidget(self.analyze_roi_button)

        self.roi_name_input = QLineEdit(self)
        self.roi_name_input.setPlaceholderText("Enter ROI Name")
        roi_controls.addWidget(self.roi_name_input)

        self.save_roi_button = QPushButton('Save ROI')
        self.save_roi_button.clicked.connect(self.save_roi)
        roi_controls.addWidget(self.save_roi_button)
        self.controls_layout.addLayout(roi_controls)

        # ROI Table
        self.roi_table = QTableWidget()
        self.initialize_roi_table()
        self.controls_layout.addWidget(self.roi_table)

        # Save to CSV Button
        self.save_csv_button = QPushButton('Save ROIs to CSV')
        self.save_csv_button.clicked.connect(self.save_to_csv)
        self.controls_layout.addWidget(self.save_csv_button)

        # ROI Graph
        self.figure, self.ax = plt.subplots()
        self.canvas = FigureCanvas(self.figure)
        self.controls_layout.addWidget(self.canvas)

        # Add controls to splitter
        splitter.addWidget(self.controls_widget)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 1)

        splitter.setSizes([int(self.width() * 0.75), int(self.width() * 0.25)])

        main_layout.addWidget(splitter)

        # Create the movable ROI before displaying the slice
        self.create_roi()

        self.show()
        self.display_slice()

    def auto_window(self):
        """Automatically adjust window and level based on the current slice and subtraction mode."""
        if self.images is None:
            print("No images to auto-window.")
            return

        # Determine if subtraction is applied
        subtraction_index = self.subtraction_combo.currentIndex() - 1  # Adjust for 'None' option

        if subtraction_index >= 0:
            # Subtraction mode: use absolute values to calculate a centered window
            subtraction_image = self.images[subtraction_index]
            current_image = self.images[self.current_slice] - subtraction_image

            # Calculate central percentiles based on absolute values in the subtraction image
            lower_percentile = np.percentile(np.abs(current_image), 5)
            upper_percentile = np.percentile(np.abs(current_image), 95)

            # Set window width to span this range, and level near zero to center the differences
            optimal_window = 2 * max(upper_percentile, abs(lower_percentile))
            optimal_level = 0
            print("Auto Window (Subtraction Mode) applied.")

        else:
            # Normal mode: calculate window based on central percentiles of the pixel values
            current_image = self.images[self.current_slice]
            lower_percentile = np.percentile(current_image, 2.5)
            upper_percentile = np.percentile(current_image, 97.5)

            # Set window and level based on the range between these percentiles
            optimal_window = upper_percentile - lower_percentile
            optimal_level = (upper_percentile + lower_percentile) / 2
            print("Auto Window applied (Normal Mode).")

        # Update sliders to the new values
        self.window_slider.setValue(int(optimal_window))
        self.level_slider.setValue(int(optimal_level))
        
        print(f"Auto Window - Window: {optimal_window}, Level: {optimal_level}")
        self.display_slice()

    def initialize_roi_table(self):
        """Initialize the ROI table with appropriate headers."""
        num_slices = self.images.shape[0]
        self.roi_table.setColumnCount(4 + num_slices)
        headers = ['Name', 'Min Value', 'Max Value', 'Difference']
        headers += [f'Slice{i}' for i in range(num_slices)]
        self.roi_table.setHorizontalHeaderLabels(headers)
        self.roi_table.horizontalHeader().setStretchLastSection(True)
        self.roi_table.setSizeAdjustPolicy(QTableWidget.AdjustToContents)
        print("ROI table initialized.")

    def create_roi(self):
        """Create a movable ROI (circular) on the image."""
        if self.roi_item:
            self.scene.removeItem(self.roi_item)
            self.roi_item = None

        self.roi_diameter = self.diameter_slider.value()
        radius = self.roi_diameter / 2
        new_roi = QGraphicsEllipseItem(-radius, -radius, self.roi_diameter, self.roi_diameter)
        new_roi.setPen(QPen(Qt.blue, 2))
        new_roi.setBrush(Qt.transparent)
        new_roi.setFlags(QGraphicsEllipseItem.ItemIsMovable | QGraphicsEllipseItem.ItemIsSelectable)
        self.scene.addItem(new_roi)

        # Center the ROI in the image
        image_height, image_width = self.images.shape[1], self.images.shape[2]
        image_center = QPointF(image_width / 2, image_height / 2)
        new_roi.setPos(image_center)
        new_roi.setZValue(1)

        self.roi_item = new_roi
        print("ROI initialized and centered on the image.")

    def display_slice(self):
        """Display the current slice with windowing and optional subtraction."""
        if self.images is None:
            print("No images to display.")
            return

        # Retrieve window and level values
        window = self.window_slider.value()
        level = self.level_slider.value()
        print(f"Displaying slice {self.current_slice} with Window: {window}, Level: {level}")

        subtraction_index = self.subtraction_combo.currentIndex() - 1
        if subtraction_index >= 0:
            if subtraction_index >= self.images.shape[0]:
                print(f"Subtraction index {subtraction_index} out of range. No subtraction applied.")
                current_image = self.images[self.current_slice].copy()
            else:
                subtraction_image = self.images[subtraction_index]
                current_image = self.images[self.current_slice] - subtraction_image
                print(f"Subtracted Image {subtraction_index} from Slice {self.current_slice}.")
        else:
            current_image = self.images[self.current_slice].copy()
            print("No subtraction applied.")

        # Apply window and level
        lower = level - (window / 2)
        upper = level + (window / 2)
        print(f"Windowing: lower={lower}, upper={upper}")

        # Clip the image to the window and level
        current_image_clipped = np.clip(current_image, lower, upper)
        print("Image clipped to window and level.")

        # Normalize the image to 0-255
        if upper - lower != 0:
            current_image_normalized = ((current_image_clipped - lower) / (upper - lower)) * 255.0
        else:
            current_image_normalized = current_image_clipped - lower

        current_image_normalized = current_image_normalized.astype(np.uint8)
        print("Image normalized to 0-255.")

        height, width = current_image_normalized.shape
        q_image = QImage(current_image_normalized.data, width, height, QImage.Format_Grayscale8)
        pixmap = QPixmap.fromImage(q_image)

        if self.pixmap_item:
            self.pixmap_item.setPixmap(pixmap)
            print("Updated existing pixmap_item.")
        else:
            self.pixmap_item = QGraphicsPixmapItem(pixmap)
            self.scene.addItem(self.pixmap_item)
            self.pixmap_item.setZValue(0)
            print("Created new pixmap_item.")

        self.graphics_view.fitInView(self.pixmap_item, Qt.KeepAspectRatio)
        self.graphics_view.setAlignment(Qt.AlignCenter)

        self.status_label.setText(f"Slice: {self.current_slice}")
        print(f"Slice {self.current_slice} displayed.")

        # Show or hide the ROI based on overlay checkbox
        if self.roi_item:
            try:
                self.roi_item.setVisible(self.overlay_checkbox.isChecked())
                print(f"ROI visibility set to {self.overlay_checkbox.isChecked()}.")
            except Exception as e:
                print(f"Error setting ROI visibility: {e}")
        else:
            print("No ROI item to set visibility.")

    def update_slice(self, value):
        """Handle slice slider movement."""
        self.current_slice = value
        print(f"Slice slider moved to {self.current_slice}.")
        self.display_slice()

    def update_window_level(self):
        """Handle window or level slider movement."""
        print("Window/Level slider moved.")
        self.display_slice()

    def update_roi_diameter(self, value):
        """Update the diameter of the ROI."""
        self.roi_diameter = value
        if self.roi_item:
            rect = QRectF(-self.roi_diameter / 2, -self.roi_diameter / 2, self.roi_diameter, self.roi_diameter)
            self.roi_item.setRect(rect)
            print(f"ROI diameter updated to {self.roi_diameter} pixels.")
        self.display_slice()

    def analyze_roi(self):
        """Analyze the ROI for the current slice."""
        if not self.overlay_checkbox.isChecked():
            QMessageBox.warning(self, "ROI Hidden", "ROI overlay is hidden. Please show the ROI to analyze.")
            print("ROI overlay is hidden. Analysis aborted.")
            return

        # Get ROI position and size
        roi_center = self.roi_item.pos()
        radius = self.roi_diameter / 2

        # Calculate bounding box
        x_start = int(roi_center.x() - radius)
        y_start = int(roi_center.y() - radius)
        diameter = int(self.roi_diameter)

        # Ensure ROI is within image boundaries
        image_height, image_width = self.images.shape[1], self.images.shape[2]
        if x_start < 0 or y_start < 0 or x_start + diameter > image_width or y_start + diameter > image_height:
            QMessageBox.warning(self, "ROI Out of Bounds", "ROI is out of image boundaries.")
            print("ROI is out of bounds.")
            return

        # Extract ROI data
        current_image = self.images[self.current_slice]
        roi_data = current_image[y_start:y_start + diameter, x_start:x_start + diameter]

        # Create a circular mask
        Y, X = np.ogrid[:diameter, :diameter]
        dist_from_center = np.sqrt((X - radius)**2 + (Y - radius)**2)
        mask = dist_from_center <= radius

        masked_roi = roi_data[mask]

        if masked_roi.size == 0:
            QMessageBox.warning(self, "Empty ROI", "ROI mask is empty.")
            print("ROI mask is empty.")
            return

        max_val = masked_roi.max()
        min_val = masked_roi.min()
        diff = max_val - min_val

        QMessageBox.information(
            self, "ROI Analysis",
            f"ROI Analysis - Max: {max_val}, Min: {min_val}, Difference: {diff}"
        )
        print(f"ROI Analysis - Max: {max_val}, Min: {min_val}, Difference: {diff}")

    def save_roi(self):
        """Save the ROI analysis across all slices and add to plot."""
        if not self.overlay_checkbox.isChecked():
            QMessageBox.warning(self, "ROI Hidden", "ROI overlay is hidden. Please show the ROI to save.")
            print("ROI overlay is hidden. Save operation aborted.")
            return

        roi_name = self.roi_name_input.text().strip()
        if not roi_name:
            QMessageBox.warning(self, "Invalid Name", "ROI name cannot be empty.")
            print("ROI name is empty. Save operation aborted.")
            return

        # Get ROI position and size
        roi_center = self.roi_item.pos()
        radius = self.roi_diameter / 2

        # Calculate bounding box
        x_start = int(roi_center.x() - radius)
        y_start = int(roi_center.y() - radius)
        diameter = int(self.roi_diameter)

        # Ensure ROI is within image boundaries
        image_height, image_width = self.images.shape[1], self.images.shape[2]
        if x_start < 0 or y_start < 0 or x_start + diameter > image_width or y_start + diameter > image_height:
            QMessageBox.warning(self, "ROI Out of Bounds", "ROI is out of image boundaries.")
            print("ROI is out of bounds. Save operation aborted.")
            return

        # Initialize list to store ROI values per slice
        roi_values = []

        for slice_idx in range(self.images.shape[0]):
            current_image = self.images[slice_idx]

            # Extract ROI data
            roi_data = current_image[y_start:y_start + diameter, x_start:x_start + diameter]

            # Create a circular mask
            Y, X = np.ogrid[:diameter, :diameter]
            dist_from_center = np.sqrt((X - radius)**2 + (Y - radius)**2)
            mask = dist_from_center <= radius

            masked_roi = roi_data[mask]

            if masked_roi.size == 0:
                roi_value = np.nan
                print(f"ROI mask is empty on slice {slice_idx}.")
            else:
                roi_value = masked_roi.mean()

            roi_values.append(roi_value)

        # Store ROI data for plotting
        self.roi_data[roi_name] = roi_values

        # Plot updated ROI data
        self.plot_roi_data()

        min_val = min(filter(lambda x: not np.isnan(x), roi_values))
        max_val = max(filter(lambda x: not np.isnan(x), roi_values))
        diff = max_val - min_val

        row_position = self.roi_table.rowCount()
        self.roi_table.insertRow(row_position)
        self.roi_table.setItem(row_position, 0, QTableWidgetItem(roi_name))
        self.roi_table.setItem(row_position, 1, QTableWidgetItem(str(min_val)))
        self.roi_table.setItem(row_position, 2, QTableWidgetItem(str(max_val)))
        self.roi_table.setItem(row_position, 3, QTableWidgetItem(str(diff)))

        for slice_idx, roi_val in enumerate(roi_values):
            roi_val_str = f"{roi_val:.2f}" if not np.isnan(roi_val) else "NaN"
            self.roi_table.setItem(row_position, 4 + slice_idx, QTableWidgetItem(roi_val_str))

        print(f"ROI '{roi_name}' saved successfully.")
        QMessageBox.information(self, "ROI Saved", f"ROI '{roi_name}' saved successfully.")

    def plot_roi_data(self):
        """Plot the ROI data for all saved ROIs."""
        self.ax.clear()
        for name, values in self.roi_data.items():
            self.ax.plot(values, label=name)
        self.ax.set_title("ROI Comparison Across Slices")
        self.ax.set_xlabel("Slice")
        self.ax.set_ylabel("Mean ROI Value")
        self.ax.legend(loc="upper right")
        self.canvas.draw()

    def save_to_csv(self):
        """Save all ROI data to a CSV file."""
        if self.roi_table.rowCount() == 0:
            QMessageBox.warning(self, "No Data", "No ROI data to save.")
            print("No ROI data to save. Save operation aborted.")
            return

        options = QFileDialog.Options()
        file_name, _ = QFileDialog.getSaveFileName(
            self, "Save ROIs to CSV", "", "CSV Files (*.csv);;All Files (*)", options=options
        )
        if not file_name:
            print("Save operation canceled.")
            return

        data = []
        headers = ['Name', 'Min Value', 'Max Value', 'Difference']
        headers += [f'Slice{i}' for i in range(self.images.shape[0])]
        for row in range(self.roi_table.rowCount()):
            row_data = []
            for col in range(self.roi_table.columnCount()):
                item = self.roi_table.item(row, col)
                if item is not None:
                    row_data.append(item.text())
                else:
                    row_data.append('')
            data.append(row_data)

        df = pd.DataFrame(data, columns=headers)
        try:
            df.to_csv(file_name, index=False)
            QMessageBox.information(self, "Save Successful", f"ROI data saved to {file_name}.")
            print(f"ROI data saved to {file_name}.")
        except Exception as e:
            QMessageBox.critical(self, "Save Failed", f"Failed to save CSV: {e}")
            print(f"Failed to save CSV: {e}")


if __name__ == '__main__':
    app = QApplication(sys.argv)
    viewer = DICOMViewer()
    sys.exit(app.exec_())
