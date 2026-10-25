/// <reference types="vite/client" />
declare module "*.vue" {
  import type { DefineComponent } from "vue";
  const component: DefineComponent<object, object, unknown>;
  export default component;
}

interface PimmichBoot {
  lang: string;
  user: string;
  admin: boolean;
  classic: string;
  edition?: "frame" | "event";  // « event » : Pimmich sur un ordinateur (pimmich_event.py), sans le matériel du Raspberry Pi
}

interface Window {
  PIMMICH?: PimmichBoot;
}
