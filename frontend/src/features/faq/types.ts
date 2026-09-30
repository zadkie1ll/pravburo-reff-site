export interface FaqItem {
  question: string;
  answer: string;
}

export interface FaqResponse {
  items: FaqItem[];
  telegram_manager_url: string;
  telegram_materials_url: string;
}
