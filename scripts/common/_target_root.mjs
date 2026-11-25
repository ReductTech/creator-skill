import fs from 'node:fs';
import path from 'node:path';

export function getTargetRoot(project = process.env.CREATOR_SKILL_PROJECT_ROOT) {
  if (!project || !path.isAbsolute(project) || !fs.statSync(project, {throwIfNoEntry: false})?.isDirectory()) {
    throw new Error('Specify an existing absolute project directory with --project');
  }
  return fs.realpathSync(project);
}
