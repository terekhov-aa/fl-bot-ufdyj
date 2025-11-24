const express = require('express');
const analyzeController = require('../controllers/analyzeController');

const router = express.Router();

router.post('/', analyzeController.analyzeLink);

module.exports = router;
