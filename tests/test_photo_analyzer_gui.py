import unittest
import threading

class TestPhotoAnalyzerGUI(unittest.TestCase):
    def test_import_and_launch(self):
        # Import here to avoid Tkinter issues in headless environments
        from src.photo_analyzer.photo_analyzer_gui import OllamaApp
        # Launch in a thread and close immediately
        def run_app():
            app = OllamaApp()
            app.after(500, app.destroy)
            app.mainloop()
        t = threading.Thread(target=run_app)
        t.start()
        t.join(timeout=2)
        self.assertFalse(t.is_alive(), "GUI did not close as expected")

if __name__ == "__main__":
    unittest.main()
