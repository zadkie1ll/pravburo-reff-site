export interface Rate {
  level: number;
  label: string;
  /** Amount as text, exactly as stored (e.g. "500.00"): no float rounding on the way. */
  amount: string;
}

export interface Rates {
  rates: Rate[];
}
