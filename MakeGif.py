import sys
import os
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QLabel, QFileDialog, QListWidget, QFrame,
                             QListWidgetItem, QProgressBar, QMessageBox, QComboBox,
                             QSlider, QCheckBox, QSizePolicy, QGridLayout, QScrollArea,
                             QSpinBox, QTabWidget)
from PyQt6.QtGui import QPixmap, QIcon, QColor, QPalette, QFont, QDrag
from PyQt6.QtCore import Qt, QSize, QTimer, QPropertyAnimation, QEasingCurve, QMimeData, QPoint
from PIL import Image
import imageio
import numpy as np
import rawpy

class ImagePreviewWidget(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("background-color: #2a2a2a; border: 1px solid #444444; border-radius: 4px;")
        self.setMinimumSize(400, 400)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_image(self, pixmap):
        if pixmap:
            scaled_pixmap = pixmap.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.setPixmap(scaled_pixmap)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.pixmap():
            self.set_image(self.pixmap().copy())

class CustomListWidget(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.setDropAction(Qt.DropAction.CopyAction)
            event.accept()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            event.setDropAction(Qt.DropAction.CopyAction)
            event.accept()
            links = []
            for url in event.mimeData().urls():
                links.append(str(url.toLocalFile()))
            self.parent().add_images(links)
        else:
            super().dropEvent(event)

class AnimatedButton(QPushButton):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
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

class ToggleButton(AnimatedButton):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setCheckable(True)
        self.toggled.connect(self.update_style)
        self.update_style(self.isChecked())

    def update_style(self, checked):
        if checked:
            self.setStyleSheet("""
                QPushButton {
                    background-color: #4a4a4a;
                    color: white;
                    border: 1px solid #555555;
                    padding: 8px 16px;
                    font-size: 14px;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #555555;
                }
            """)
        else:
            self.setStyleSheet("""
                QPushButton {
                    background-color: #3a3a3a;
                    color: white;
                    border: 1px solid #444444;
                    padding: 8px 16px;
                    font-size: 14px;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #4a4a4a;
                }
            """)

class ThumbnailWidget(QWidget):
    def __init__(self, image_path, parent=None):
        super().__init__(parent)
        self.image_path = image_path
        self.layout = QVBoxLayout(self)
        self.image_label = QLabel(self)
        self.text_label = QLabel(os.path.basename(image_path), self)
        self.text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.image_label)
        self.layout.addWidget(self.text_label)
        self.setFixedSize(120, 120)
        self.load_thumbnail()

    def load_thumbnail(self):
        pixmap = QPixmap(self.image_path)
        scaled_pixmap = pixmap.scaled(100, 100, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self.image_label.setPixmap(scaled_pixmap)

class GifCreatorApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SeanKD_Photos GIF Creator")
        self.setGeometry(100, 100, 1200, 800)
        self.dark_mode = True
        self.images = []
        self.current_image_index = 0
        self.fps = 24
        self.is_playing = False
        self.play_timer = QTimer(self)
        self.play_timer.timeout.connect(self.next_frame)
        self.undo_stack = []
        self.redo_stack = []

        self.init_ui()
        self.set_theme()

    def init_ui(self):
        central_widget = QWidget()
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

        # Top section: Workflow controls
        workflow_layout = QHBoxLayout()
        self.select_button = AnimatedButton("Select Images")
        self.select_button.clicked.connect(self.select_images)
        self.select_button.setToolTip("Select images to create a GIF")
        workflow_layout.addWidget(self.select_button)

        self.fps_combo = QComboBox(self)
        self.fps_combo.addItems(["6", "12", "24", "30", "48", "60"])
        self.fps_combo.setCurrentText("24")
        self.fps_combo.currentTextChanged.connect(self.update_fps)
        self.fps_combo.setToolTip("Set the frames per second for the GIF")
        workflow_layout.addWidget(QLabel("Frame Rate:"))
        workflow_layout.addWidget(self.fps_combo)

        self.undo_button = AnimatedButton("Undo")
        self.undo_button.clicked.connect(self.undo)
        self.undo_button.setToolTip("Undo the last action")
        workflow_layout.addWidget(self.undo_button)

        self.redo_button = AnimatedButton("Redo")
        self.redo_button.clicked.connect(self.redo)
        self.redo_button.setToolTip("Redo the last undone action")
        workflow_layout.addWidget(self.redo_button)

        self.theme_toggle = ToggleButton("Dark Mode")
        self.theme_toggle.setChecked(True)
        self.theme_toggle.toggled.connect(self.toggle_theme)
        self.theme_toggle.setToolTip("Toggle between dark and light mode")
        workflow_layout.addWidget(self.theme_toggle)

        workflow_layout.addStretch()

        main_layout.addLayout(workflow_layout)

        # Middle section: Image preview and frame list
        middle_section = QHBoxLayout()
        
        # Image preview
        preview_layout = QVBoxLayout()
        self.preview_widget = ImagePreviewWidget(self)
        preview_layout.addWidget(self.preview_widget)
        
        # Preview controls
        preview_controls = QHBoxLayout()
        self.play_button = AnimatedButton("Play")
        self.play_button.clicked.connect(self.toggle_play)
        self.play_button.setToolTip("Play/Pause the GIF preview")
        self.prev_frame_button = AnimatedButton("◀")
        self.prev_frame_button.clicked.connect(self.prev_frame)
        self.prev_frame_button.setToolTip("Go to previous frame")
        self.next_frame_button = AnimatedButton("▶")
        self.next_frame_button.clicked.connect(self.next_frame)
        self.next_frame_button.setToolTip("Go to next frame")
        preview_controls.addWidget(self.play_button)
        preview_controls.addWidget(self.prev_frame_button)
        preview_controls.addWidget(self.next_frame_button)
        preview_layout.addLayout(preview_controls)

        # Zoom control
        zoom_layout = QHBoxLayout()
        zoom_layout.addWidget(QLabel("Zoom:"))
        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setRange(50, 200)
        self.zoom_slider.setValue(100)
        self.zoom_slider.valueChanged.connect(self.update_zoom)
        self.zoom_slider.setToolTip("Adjust the zoom level of the preview")
        zoom_layout.addWidget(self.zoom_slider)
        preview_layout.addLayout(zoom_layout)
        
        middle_section.addLayout(preview_layout)
        
        # Frame list
        list_layout = QVBoxLayout()
        self.tab_widget = QTabWidget()
        self.image_list = CustomListWidget(self)
        self.image_list.itemSelectionChanged.connect(self.on_select_image)
        self.thumbnail_widget = QWidget()
        self.thumbnail_layout = QGridLayout(self.thumbnail_widget)
        self.tab_widget.addTab(self.image_list, "List View")
        self.tab_widget.addTab(self.thumbnail_widget, "Thumbnail View")
        list_buttons_layout = QHBoxLayout()
        self.remove_button = AnimatedButton("Remove Frame")
        self.remove_button.clicked.connect(self.remove_selected_frame)
        self.remove_button.setToolTip("Remove the selected frame")
        list_buttons_layout.addWidget(self.remove_button)
        list_layout.addWidget(QLabel("Frames:"))
        list_layout.addWidget(self.tab_widget)
        list_layout.addLayout(list_buttons_layout)
        
        middle_section.addLayout(list_layout)
        main_layout.addLayout(middle_section)

        # Bottom section: Optimization options
        optimization_layout = QHBoxLayout()
        optimization_layout.addWidget(QLabel("Optimization:"))
        self.optimize_toggle = ToggleButton("Optimize")
        self.optimize_toggle.setChecked(True)
        self.optimize_toggle.setToolTip("Toggle GIF optimization")
        optimization_layout.addWidget(self.optimize_toggle)
        
        optimization_layout.addWidget(QLabel("Quality:"))
        self.quality_slider = QSlider(Qt.Orientation.Horizontal)
        self.quality_slider.setRange(1, 100)
        self.quality_slider.setValue(85)
        self.quality_slider.setFixedWidth(200)
        self.quality_slider.setToolTip("Adjust the quality of the GIF")
        self.quality_label = QLabel("85")
        self.quality_slider.valueChanged.connect(self.update_quality_label)
        optimization_layout.addWidget(self.quality_slider)
        optimization_layout.addWidget(self.quality_label)
        
        optimization_layout.addStretch()
        main_layout.addLayout(optimization_layout)

        # Export options
        export_layout = QHBoxLayout()
        export_layout.addWidget(QLabel("Export Options:"))
        
        self.resolution_combo = QComboBox(self)
        self.resolution_combo.addItems(["Original", "1080p", "720p", "480p", "360p"])
        self.resolution_combo.setToolTip("Select the output resolution")
        export_layout.addWidget(QLabel("Resolution:"))
        export_layout.addWidget(self.resolution_combo)

        self.loop_count_spin = QSpinBox(self)
        self.loop_count_spin.setRange(0, 100)
        self.loop_count_spin.setValue(0)
        self.loop_count_spin.setToolTip("Set the number of loops (0 for infinite)")
        export_layout.addWidget(QLabel("Loop Count:"))
        export_layout.addWidget(self.loop_count_spin)

        self.output_format_combo = QComboBox(self)
        self.output_format_combo.addItems(["GIF", "WebP"])
        self.output_format_combo.setToolTip("Select the output format")
        export_layout.addWidget(QLabel("Output Format:"))
        export_layout.addWidget(self.output_format_combo)

        export_layout.addStretch()
        main_layout.addLayout(export_layout)

        # Create GIF button (moved to bottom right)
        create_gif_layout = QHBoxLayout()
        create_gif_layout.addStretch()
        self.create_button = AnimatedButton("Create GIF")
        self.create_button.clicked.connect(self.create_gif)
        self.create_button.setToolTip("Create the GIF from selected images")
        create_gif_layout.addWidget(self.create_button)
        main_layout.addLayout(create_gif_layout)

        # Progress bar
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)

        # Set up keyboard shortcuts
        self.setup_shortcuts()

    def setup_shortcuts(self):
        QApplication.instance().setAttribute(Qt.ApplicationAttribute.AA_DontShowIconsInMenus, False)
        self.select_shortcut = self.addAction("Select Images")
        self.select_shortcut.setShortcut("Ctrl+O")
        self.select_shortcut.triggered.connect(self.select_images)

        self.play_shortcut = self.addAction("Play/Pause")
        self.play_shortcut.setShortcut("Space")
        self.play_shortcut.triggered.connect(self.toggle_play)

        self.create_shortcut = self.addAction("Create GIF")
        self.create_shortcut.setShortcut("Ctrl+S")
        self.create_shortcut.triggered.connect(self.create_gif)

        self.undo_shortcut = self.addAction("Undo")
        self.undo_shortcut.setShortcut("Ctrl+Z")
        self.undo_shortcut.triggered.connect(self.undo)

        self.redo_shortcut = self.addAction("Redo")
        self.redo_shortcut.setShortcut("Ctrl+Y")
        self.redo_shortcut.triggered.connect(self.redo)

    def set_theme(self):
        if self.dark_mode:
            self.setStyleSheet("""
                QMainWindow, QWidget {
                    background-color: #1e1e1e;
                    color: #cccccc;
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
                    image: url(down_arrow_dark.png);
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
                QSlider::groove:horizontal {
                    border: 1px solid #444444;
                    height: 8px;
                    background: #2a2a2a;
                    margin: 2px 0;
                }
                QSlider::handle:horizontal {
                    background: #4a4a4a;
                    border: 1px solid #555555;
                    width: 18px;
                    margin: -2px 0;
                    border-radius: 3px;
                }
            """)
        else:
            self.setStyleSheet("""
                QMainWindow, QWidget {
                    background-color: #f0f0f0;
                    color: #333333;
                }
                QLabel {
                    color: #333333;
                    font-size: 14px;
                }
                QComboBox, QSpinBox {
                    background-color: #ffffff;
                    color: #333333;
                    border: 1px solid #cccccc;
                    padding: 5px;
                    border-radius: 4px;
                }
                QComboBox::drop-down, QSpinBox::down-button {
                    subcontrol-origin: padding;
                    subcontrol-position: top right;
                    width: 15px;
                    border-left-width: 1px;
                    border-left-color: #cccccc;
                    border-left-style: solid;
                }
                QComboBox::down-arrow, QSpinBox::down-arrow {
                    image: url(down_arrow_light.png);
                }
                QCheckBox {
                    color: #333333;
                }
                QCheckBox::indicator {
                    width: 13px;
                    height: 13px;
                }
                QCheckBox::indicator:unchecked {
                    border: 1px solid #cccccc;
                    background-color: #ffffff;
                }
                QCheckBox::indicator:checked {
                    border: 1px solid #cccccc;
                    background-color: #e0e0e0;
                }
                QSlider::groove:horizontal {
                    border: 1px solid #cccccc;
                    height: 8px;
                    background: #ffffff;
                    margin: 2px 0;
                }
                QSlider::handle:horizontal {
                    background: #e0e0e0;
                    border: 1px solid #cccccc;
                    width: 18px;
                    margin: -2px 0;
                    border-radius: 3px;
                }
            """)

        # Update specific widget styles
        self.update_widget_styles()

    def update_widget_styles(self):
        button_style = """
            QPushButton {
                background-color: #4a4a4a;
                color: #ffffff;
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
        """ if self.dark_mode else """
            QPushButton {
                background-color: #e0e0e0;
                color: #333333;
                border: 1px solid #cccccc;
                padding: 8px 16px;
                font-size: 14px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #d0d0d0;
                border: 1px solid #bbbbbb;
            }
            QPushButton:pressed {
                background-color: #c0c0c0;
            }
        """

        for button in [self.select_button, self.undo_button, self.redo_button, 
                       self.play_button, self.prev_frame_button, self.next_frame_button, self.remove_button]:
            button.setStyleSheet(button_style)

        # Special style for Create GIF button
        create_gif_style = """
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: 1px solid #45a049;
                padding: 8px 16px;
                font-size: 14px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
        """
        self.create_button.setStyleSheet(create_gif_style)

        list_style = """
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
        """ if self.dark_mode else """
            QListWidget {
                background-color: #ffffff;
                border: 1px solid #cccccc;
                border-radius: 4px;
            }
            QListWidget::item {
                color: #333333;
                border-bottom: 1px solid #e0e0e0;
                padding: 5px;
            }
            QListWidget::item:selected {
                background-color: #e0e0e0;
                color: #333333;
            }
        """
        self.image_list.setStyleSheet(list_style)

        progress_style = """
            QProgressBar {
                border: 1px solid #444444;
                border-radius: 4px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #3a3a3a;
            }
        """ if self.dark_mode else """
            QProgressBar {
                border: 1px solid #cccccc;
                border-radius: 4px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #e0e0e0;
            }
        """
        self.progress_bar.setStyleSheet(progress_style)

    def toggle_theme(self, checked):
        self.dark_mode = checked
        self.set_theme()

    def update_quality_label(self, value):
        self.quality_label.setText(str(value))

    def select_images(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select Images", "", "Image Files (*.png *.jpg *.jpeg *.gif *.bmp *.dng)")
        if files:
            self.add_images(files)

    def add_images(self, files):
        old_images = self.images.copy()
        self.images.extend(files)
        self.update_image_list()
        self.show_image(len(old_images))
        self.add_to_undo_stack(("add_images", old_images, self.images.copy()))

    def update_image_list(self):
        self.image_list.clear()
        for i, img in enumerate(self.images):
            item = QListWidgetItem(os.path.basename(img))
            item.setIcon(QIcon(img))
            self.image_list.addItem(item)
        
        self.update_thumbnail_view()

    def update_thumbnail_view(self):
        # Clear existing thumbnails
        for i in reversed(range(self.thumbnail_layout.count())): 
            self.thumbnail_layout.itemAt(i).widget().setParent(None)

        # Add new thumbnails
        for i, img_path in enumerate(self.images):
            thumbnail = ThumbnailWidget(img_path)
            row = i // 4
            col = i % 4
            self.thumbnail_layout.addWidget(thumbnail, row, col)

    def show_image(self, index):
        if 0 <= index < len(self.images):
            pixmap = QPixmap(self.images[index])
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
            old_images = self.images.copy()
            del self.images[current_row]
            self.update_image_list()
            if self.images:
                self.show_image(min(current_row, len(self.images) - 1))
            else:
                self.preview_widget.clear()
            self.add_to_undo_stack(("remove_frame", old_images, self.images.copy()))

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

    def update_zoom(self, value):
        if self.preview_widget.pixmap():
            scale_factor = value / 100.0
            original_pixmap = QPixmap(self.images[self.current_image_index])
            scaled_pixmap = original_pixmap.scaled(
                original_pixmap.size() * scale_factor,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.preview_widget.set_image(scaled_pixmap)

    def add_to_undo_stack(self, action):
        self.undo_stack.append(action)
        self.redo_stack.clear()

    def undo(self):
        if self.undo_stack:
            action = self.undo_stack.pop()
            self.redo_stack.append(action)
            action_type, old_state, new_state = action
            self.images = old_state
            self.update_image_list()
            self.show_image(0)

    def redo(self):
        if self.redo_stack:
            action = self.redo_stack.pop()
            self.undo_stack.append(action)
            action_type, old_state, new_state = action
            self.images = new_state
            self.update_image_list()
            self.show_image(0)

    def create_gif(self):
        if not self.images:
            QMessageBox.warning(self, "No Images", "Please select images before creating a GIF.")
            return

        output_format = self.output_format_combo.currentText().lower()
        file_filter = f"{output_format.upper()} Files (*.{output_format})"
        output_file, _ = QFileDialog.getSaveFileName(self, f"Save {output_format.upper()}", "", file_filter)
        
        if output_file:
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            
            images = []
            for i, file_name in enumerate(self.images):
                if file_name.lower().endswith('.dng'):
                    with rawpy.imread(file_name) as raw:
                        img = raw.postprocess()
                        img = Image.fromarray(img)
                else:
                    img = Image.open(file_name)
                
                if img.mode == 'RGBA':
                    img = img.convert('RGB')
                
                # Apply resolution change if needed
                resolution = self.resolution_combo.currentText()
                if resolution != "Original":
                    height = int(resolution[:-1])
                    ratio = height / img.size[1]
                    new_width = int(img.size[0] * ratio)
                    img = img.resize((new_width, height), Image.LANCZOS)
                
                if self.optimize_toggle.isChecked():
                    img = img.copy()
                    img.thumbnail((800, 800), Image.LANCZOS)
                
                img_array = np.array(img)
                images.append(img_array)
                self.progress_bar.setValue(int((i + 1) / len(self.images) * 50))
                QApplication.processEvents()

            if images:
                loop = self.loop_count_spin.value()
                if output_format == 'gif':
                    kwargs = {'fps': self.fps, 'loop': loop}
                    if self.optimize_toggle.isChecked():
                        kwargs['optimize'] = True
                        kwargs['quality'] = self.quality_slider.value()
                    
                    imageio.mimsave(output_file, images, format='gif', **kwargs)
                elif output_format == 'webp':
                    kwargs = {'fps': self.fps, 'loop': loop, 'quality': self.quality_slider.value()}
                    imageio.mimsave(output_file, images, format='webp', **kwargs)
                
                self.progress_bar.setValue(100)
                QTimer.singleShot(1000, lambda: self.progress_bar.setVisible(False))
                QMessageBox.information(self, "Success", f"{output_format.upper()} created successfully: {output_file}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = GifCreatorApp()
    window.show()
    sys.exit(app.exec())