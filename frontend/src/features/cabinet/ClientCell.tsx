/** Table cell with a client's name and masked phone (stacked on narrow screens). */
export function ClientCell({ name, maskedPhone }: { name: string; maskedPhone: string }) {
  return (
    <td data-label="Клиент">
      {name}
      <br />
      <span className="nowrap">{maskedPhone}</span>
    </td>
  );
}
