export interface FaqEntry {
  id: number;
  question: string;
  answer: string;
}

export interface FaqList {
  items: FaqEntry[];
}

export type MoveDirection = "up" | "down";
