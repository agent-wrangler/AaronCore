import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class FrontendImageUploadBridgeTests(unittest.TestCase):
    def test_composer_no_longer_blocks_upload_by_model_vision_flag(self):
        text = (ROOT / "static/js/chat/composer.js").read_text(encoding="utf-8")
        self.assertIn("function _canUseVisionUpload(){", text)
        self.assertIn("return true;", text)
        self.assertNotIn("Configure a vision-capable model before uploading images.", text)
        self.assertNotIn("if(!_canUseVisionUpload()){\n  _notifyVisionUploadUnavailable();", text)

    def test_model_button_state_no_longer_depends_on_any_vision_model(self):
        text = (ROOT / "static/js/app/models.js").read_text(encoding="utf-8")
        self.assertIn("btn.classList.remove('is-inactive');", text)
        self.assertIn("btn.title=t('model.upload.title');", text)
        self.assertNotIn("var anyVision=Object.keys(models).some(function(k){return models[k].vision;});", text)


if __name__ == "__main__":
    unittest.main()
