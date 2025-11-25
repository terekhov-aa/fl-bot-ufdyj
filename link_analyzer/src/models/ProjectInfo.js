// FILE: link_analyzer/src/models/ProjectInfo.js
class ProjectInfo {
  constructor() {
    this.projectType = '';
    this.summary = '';
    this.targetAudience = '';
    this.mainFlows = [];
    this.mainFeatures = [];
    this.techStackGuess = [];
    this.complexity = 'unknown';
    this.risks = [];
    this.tasksForFreelancer = [];
  }
}

module.exports = ProjectInfo;
