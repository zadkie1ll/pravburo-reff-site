import { useLogout } from "./api";

export function LogoutButton() {
  const logout = useLogout();
  return (
    <button
      className="button secondary"
      type="button"
      disabled={logout.isPending}
      onClick={() => logout.mutate()}
    >
      Выйти
    </button>
  );
}
