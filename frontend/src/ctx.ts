import { createContext, useContext } from "react";

export type Route =
  | "dashboard" | "merge" | "images" | "organize" | "split" | "compress"
  | "extract" | "toimages" | "media" | "history" | "settings";

export const NavContext = createContext<{
  route: Route;
  navigate: (r: Route) => void;
}>({ route: "dashboard", navigate: () => {} });

export const useNav = () => useContext(NavContext);

export interface Toast {
  id: number;
  kind: "success" | "error" | "info";
  text: string;
}

export const ToastContext = createContext<{
  toasts: Toast[];
  push: (kind: Toast["kind"], text: string) => void;
  dismiss: (id: number) => void;
}>({ toasts: [], push: () => {}, dismiss: () => {} });

export const useToast = () => useContext(ToastContext);
