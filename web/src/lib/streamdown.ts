import { code } from "@streamdown/code";
import type { PluginConfig, ThemeInput } from "streamdown";

export const STREAMDOWN_PLUGINS = { code } satisfies PluginConfig;

export const STREAMDOWN_SHIKI_THEME: [ThemeInput, ThemeInput] = [
	"light-plus",
	"dark-plus",
];
