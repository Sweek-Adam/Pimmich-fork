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
}

interface Window {
  PIMMICH?: PimmichBoot;
}
