import sys
import os
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QLabel, QFileDialog, QListWidget, QFrame,
                             QListWidgetItem, QProgressBar, QMessageBox, QComboBox,
                             QSpinBox, QCheckBox)
from PyQt6.QtGui import QPixmap, QIcon, QColor, QPalette, QFontDatabase, QFont
from PyQt6.QtCore import Qt, QSize, QTimer, QPropertyAnimation, QEasingCurve
from PIL import Image
import imageio
import numpy as np

class ImagePreviewWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.image_label = QLabel(self)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.image_label)
        self.setStyleSheet("background-color: #2a2a2a; border: 1px solid #444444; border-radius: 4px;")

    def set_image(self, pixmap):
        self.image_label.setPixmap(pixmap)

class CustomListWidget(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QListWidget {
                background-color: #2a2a2a;
                border: 1px solid #444444;
                border-radius: 4px;
            }
            QListWidget::item {
                color: #cccccc;
                border-bottom: 1px solid #444444;
                padding: 5px;
            }
            QListWidget::item:selected {
                background-color: #3a3a3a;
                color: #ffffff;
            }
        """)

class AnimatedButton(QPushButton):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setStyleSheet("""
            QPushButton {
                background-color: #4a4a4a;
                color: #cccccc;
                border: 1px solid #555555;
                padding: 8px 16px;
                font-size: 14px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #555555;
                border: 1px solid #666666;
            }
            QPushButton:pressed {
                background-color: #333333;
            }
        """)
        self._animation = QPropertyAnimation(self, b"geometry")
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._animation.setDuration(100)

    def mousePressEvent(self, event):
        self._animation.setStartValue(self.geometry())
        self._animation.setEndValue(self.geometry().adjusted(1, 1, -1, -1))
        self._animation.start()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self._animation.setStartValue(self.geometry())
        self._animation.setEndValue(self.geometry().adjusted(-1, -1, 1, 1))
        self._animation.start()
        super().mouseReleaseEvent(event)

class GifCreatorApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Advanced Professional GIF Creator")
        self.setGeometry(100, 100, 1200, 800)
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1e1e1e;
            }
            QLabel {
                color: #cccccc;
                font-size: 14px;
            }
            QComboBox, QSpinBox {
                background-color: #2a2a2a;
                color: #cccccc;
                border: 1px solid #444444;
                padding: 5px;
                border-radius: 4px;
            }
            QComboBox::drop-down, QSpinBox::down-button {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 15px;
                border-left-width: 1px;
                border-left-color: #444444;
                border-left-style: solid;
            }
            QComboBox::down-arrow, QSpinBox::down-arrow {
                image: url(down_arrow.png);
            }
            QCheckBox {
                color: #cccccc;
            }
            QCheckBox::indicator {
                width: 13px;
                height: 13px;
            }
            QCheckBox::indicator:unchecked {
                border: 1px solid #555555;
                background-color: #2a2a2a;
            }
            QCheckBox::indicator:checked {
                border: 1px solid #555555;
                background-color: #3a3a3a;
            }
        """)

        self.images = []
        self.current_image_index = 0
        self.fps = 24
        self.is_playing = False
        self.play_timer = QTimer(self)
        self.play_timer.timeout.connect(self.next_frame)

        self.init_ui()

    def init_ui(self):
        central_widget = QWidget()
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

        # Top section: Workflow controls
        workflow_layout = QHBoxLayout()
        self.select_button = AnimatedButton("Select Images")
        self.select_button.clicked.connect(self.select_images)
        workflow_layout.addWidget(self.select_button)

        self.fps_combo = QComboBox(self)
        self.fps_combo.addItems(["6", "12", "24", "30", "48", "60"])
        self.fps_combo.setCurrentText("24")
        self.fps_combo.currentTextChanged.connect(self.update_fps)
        workflow_layout.addWidget(QLabel("Frame Rate:"))
        workflow_layout.addWidget(self.fps_combo)

        self.create_button = AnimatedButton("Create GIF")
        self.create_button.clicked.connect(self.create_gif)
        workflow_layout.addWidget(self.create_button)
        workflow_layout.addStretch()

        main_layout.addLayout(workflow_layout)

        # Middle section: Image preview and frame list
        middle_section = QHBoxLayout()
        
        # Image preview
        preview_layout = QVBoxLayout()
        self.preview_widget = ImagePreviewWidget(self)
        self.preview_widget.setFixedSize(600, 600)
        preview_layout.addWidget(self.preview_widget)
        
        # Preview controls
        preview_controls = QHBoxLayout()
        self.play_button = AnimatedButton("Play")
        self.play_button.clicked.connect(self.toggle_play)
        self.prev_frame_button = AnimatedButton("◀")
        self.prev_frame_button.clicked.connect(self.prev_frame)
        self.next_frame_button = AnimatedButton("▶")
        self.next_frame_button.clicked.connect(self.next_frame)
        preview_controls.addWidget(self.play_button)
        preview_controls.addWidget(self.prev_frame_button)
        preview_controls.addWidget(self.next_frame_button)
        preview_layout.addLayout(preview_controls)
        
        middle_section.addLayout(preview_layout)
        
        # Frame list
        list_layout = QVBoxLayout()
        self.image_list = CustomListWidget(self)
        self.image_list.itemSelectionChanged.connect(self.on_select_image)
        list_buttons_layout = QHBoxLayout()
        self.remove_button = AnimatedButton("Remove Frame")
        self.remove_button.clicked.connect(self.remove_selected_frame)
        list_buttons_layout.addWidget(self.remove_button)
        list_layout.addWidget(QLabel("Frames:"))
        list_layout.addWidget(self.image_list)
        list_layout.addLayout(list_buttons_layout)
        
        middle_section.addLayout(list_layout)
        main_layout.addLayout(middle_section)

        # Bottom section: Optimization options
        optimization_layout = QHBoxLayout()
        optimization_layout.addWidget(QLabel("Optimization:"))
        self.compress_checkbox = QCheckBox("Compress")
        optimization_layout.addWidget(self.compress_checkbox)
        optimization_layout.addWidget(QLabel("Quality:"))
        self.quality_spinbox = QSpinBox()
        self.quality_spinbox.setRange(1, 100)
        self.quality_spinbox.setValue(85)
        optimization_layout.addWidget(self.quality_spinbox)
        optimization_layout.addStretch()
        main_layout.addLayout(optimization_layout)

        # Progress bar
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #444444;
                border-radius: 4px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #3a3a3a;
            }
        """)
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)

    def select_images(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select Images", "", "Image Files (*.png *.jpg *.jpeg *.gif *.bmp)")
        if files:
            self.images = files
            self.update_image_list()
            self.show_image(0)

    def update_image_list(self):
        self.image_list.clear()
        for img in self.images:
            item = QListWidgetItem(os.path.basename(img))
            item.setIcon(QIcon(img))
            self.image_list.addItem(item)

    def show_image(self, index):
        if 0 <= index < len(self.images):
            pixmap = QPixmap(self.images[index])
            pixmap = pixmap.scaled(QSize(580, 580), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.preview_widget.set_image(pixmap)
            self.current_image_index = index
            self.image_list.setCurrentRow(index)

    def on_select_image(self):
        selected_items = self.image_list.selectedItems()
        if selected_items:
            index = self.image_list.row(selected_items[0])
            self.show_image(index)

    def remove_selected_frame(self):
        current_row = self.image_list.currentRow()
        if current_row != -1:
            del self.images[current_row]
            self.update_image_list()
            if self.images:
                self.show_image(min(current_row, len(self.images) - 1))
            else:
                self.preview_widget.set_image(QPixmap())

    def update_fps(self, value):
        self.fps = int(value)

    def toggle_play(self):
        if self.is_playing:
            self.play_timer.stop()
            self.play_button.setText("Play")
        else:
            self.play_timer.start(1000 // self.fps)
            self.play_button.setText("Pause")
        self.is_playing = not self.is_playing

    def next_frame(self):
        self.show_image((self.current_image_index + 1) % len(self.images))

    def prev_frame(self):
        self.show_image((self.current_image_index - 1) % len(self.images))

    def create_gif(self):
        if not self.images:
            QMessageBox.warning(self, "No Images", "Please select images before creating a GIF.")
            return

        output_file, _ = QFileDialog.getSaveFileName(self, "Save GIF", "", "GIF Files (*.gif)")
        if output_file:
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            
            images = []
            for i, file_name in enumerate(self.images):
                img = Image.open(file_name)
                
                if img.mode == 'RGBA':
                    img = img.convert('RGB')
                
                if self.compress_checkbox.isChecked():
                    img = img.copy()
                    img.thumbnail((800, 800), Image.LANCZOS)
                
                img_array = np.array(img)
                images.append(img_array)
                self.progress_bar.setValue(int((i + 1) / len(self.images) * 100))
                QApplication.processEvents()

            if images:
                kwargs = {'fps': self.fps, 'loop': 0}
                if self.compress_checkbox.isChecked():
                    kwargs['optimize'] = True
                    kwargs['quality'] = self.quality_spinbox.value()
                
                imageio.mimsave(output_file, images, **kwargs)
                self.progress_bar.setValue(100)
                QTimer.singleShot(1000, lambda: self.progress_bar.setVisible(False))
                QMessageBox.information(self, "Success", f"GIF created successfully: {output_file}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = GifCreatorApp()
    window.show()
    sys.exit(app.exec())