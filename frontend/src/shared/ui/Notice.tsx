export interface NoticeState {
  kind: "success" | "error";
  text: string;
}

export function Notice({ notice }: { notice: NoticeState | null }) {
  if (!notice) return null;
  return notice.kind === "success" ? (
    <div className="notice-success" role="status">
      {notice.text}
    </div>
  ) : (
    <div className="alert" role="alert">
      {notice.text}
    </div>
  );
}
