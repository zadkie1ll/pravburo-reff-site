export interface AdminSection {
  title: string;
  description: string;
  url: string;
}

export interface AdminPanel {
  sections: AdminSection[];
}
