import { useMutation, useQueryClient } from "@tanstack/react-query";

/**
 * A mutation after which the list it changed is reloaded: the server stays the source of
 * truth, so the screen shows what was really saved (or what it refused to save).
 */
export function useInvalidatingMutation<Vars>(
  invalidate: readonly unknown[],
  action: (vars: Vars) => Promise<unknown>,
) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: action,
    onSettled: () => client.invalidateQueries({ queryKey: invalidate }),
  });
}
