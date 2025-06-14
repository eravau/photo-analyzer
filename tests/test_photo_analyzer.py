import unittest
import base64
import os
from photo_analyzer import load_image_as_base64, OllamaResponse

class TestPhotoAnalyzer(unittest.TestCase):
    def setUp(self):
        # Create a small dummy image file for testing
        self.test_image_path = "test_image.jpg"
        with open(self.test_image_path, "wb") as f:
            f.write(base64.b64decode(
                b"/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAAEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQH/wAALCAABAAEBAREA/8QAFQABAQAAAAAAAAAAAAAAAAAAAAb/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFQEBAQAAAAAAAAAAAAAAAAAAAgP/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIRAxEAPwD9/wD/2Q=="
            ))  # 1x1 px JPEG

    def tearDown(self):
        if os.path.exists(self.test_image_path):
            os.remove(self.test_image_path)

    def test_load_image_as_base64(self):
        b64 = load_image_as_base64(self.test_image_path)
        self.assertIsInstance(b64, str)
        # Should decode back to original bytes
        with open(self.test_image_path, "rb") as f:
            original = f.read()
        self.assertEqual(base64.b64decode(b64), original)

    def test_ollama_response_dataclass(self):
        data = {
            "model": "llava",
            "created_at": "now",
            "response": "test",
            "done": True,
            "done_reason": "stop",
            "context": None,
            "total_duration": 1,
            "load_duration": 2,
            "prompt_eval_count": 3,
            "prompt_eval_duration": 4,
            "eval_count": 5,
            "eval_duration": 6
        }
        resp = OllamaResponse(**data)
        self.assertEqual(resp.model, "llava")
        self.assertTrue(resp.done)
        self.assertEqual(resp.response, "test")

if __name__ == "__main__":
    unittest.main()
