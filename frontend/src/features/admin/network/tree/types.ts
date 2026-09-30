export interface TreeNode {
  id: number;
  name: string;
  email: string | null;
  phone: string | null;
  is_active: boolean;
  children: TreeNode[];
}

export interface AgentMatch {
  id: number;
  label: string;
  email: string | null;
}

export interface NetworkTreeResponse {
  matches: AgentMatch[];
  root: { id: number; label: string } | null;
  tree: TreeNode | null;
}
