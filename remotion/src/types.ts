export type Narrative = {
  hook?: string;
  body?: string;
  call_to_action?: string;
};

export type Project = {
  name: string;
  url?: string;
  description?: string;
  language?: string;
  stars?: number;
  license?: string;
  topics?: string[];
  preview_image?: string;
  public_preview_image?: string;
  star_history_image?: string;
  star_history_chart?: string;
  narrative?: Narrative;
};

export type Scene = {
  type: 'title' | 'project' | 'ending';
  durationSeconds: number;
  durationFrames: number;
  audio?: string;
  project?: Project;
  index?: number;
};

export type TrendingVideoProps = {
  date: string;
  fps: number;
  scenes: Scene[];
};

export type SceneSegmentProps = {
  date: string;
  fps?: number;
  scenes?: Scene[];
  scene: Scene;
  sceneIndex?: number;
};
