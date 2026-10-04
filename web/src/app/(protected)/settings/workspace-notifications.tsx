"use client";

import { useCallback, useEffect, useState } from "react";
import { Check, CircleHelp, Copy, MessageCircle, Send } from "lucide-react";
import { HeaderButton } from "@/components/layout/subpage-header";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { getApiErrorMessage, isApiError } from "@/lib/api/errors";
import * as notificationsApi from "@/lib/api/resources/notifications";
import type {
  DiscordNotificationSettings,
  SlackNotificationSettings,
  TelegramNotificationSettings,
} from "@/types/notifications";

interface Props {
  onForbidden: () => void;
}

type Provider = "slack" | "telegram" | "discord";

const labelClass =
  "mb-1.5 block text-[12px] font-semibold text-subtle dark:text-panel-body";

const tutorials: Record<Provider, { title: string; steps: string[] }> = {
  slack: {
    title: "Connect Slack",
    steps: [
      "Create a Slack app from scratch in api.slack.com/apps.",
      "Add a bot token with chat:write, users:read and users:read.email scopes, then install the app.",
      "Subscribe the app to message and assistant thread events using the Events request URL below.",
      "Enable interactivity and paste the Interactions request URL, then copy the bot token and signing secret here.",
    ],
  },
  telegram: {
    title: "Connect Telegram",
    steps: [
      "Open @BotFather in Telegram and send /newbot.",
      "Choose the bot name and username, then copy the HTTP API token.",
      "Paste the token below and save. auxilia validates it and registers the webhook automatically.",
      "Users generate a code in Settings → Connected accounts, then send /link CODE to the bot.",
    ],
  },
  discord: {
    title: "Connect Discord",
    steps: [
      "Create an application in the Discord Developer Portal and add a bot.",
      "Copy the Application ID, Public Key and bot token into the fields below.",
      "Save, then paste the Interactions Endpoint URL below into General Information.",
      "Use the generated Install bot link to add the app to your server. The /auxilia command may take a few minutes to appear globally.",
    ],
  },
};

function TutorialButton({ provider }: { provider: Provider }) {
  const [open, setOpen] = useState(false);
  const tutorial = tutorials[provider];
  return (
    <>
      <button
        type="button"
        aria-label={`How to configure ${provider}`}
        onClick={() => {
          setOpen(true);
        }}
        className="flex size-7 cursor-pointer items-center justify-center rounded-[7px] text-meta transition-colors hover:bg-hover hover:text-foreground"
      >
        <CircleHelp className="size-4" />
      </button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{tutorial.title}</DialogTitle>
            <DialogDescription>
              Follow these steps, then save the credentials.
            </DialogDescription>
          </DialogHeader>
          <ol className="space-y-3">
            {tutorial.steps.map((step, index) => (
              <li
                key={step}
                className="flex gap-3 text-[13px] leading-5 text-subtle"
              >
                <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-hover text-[11px] font-bold text-petrol">
                  {index + 1}
                </span>
                <span>{step}</span>
              </li>
            ))}
          </ol>
        </DialogContent>
      </Dialog>
    </>
  );
}

function CopyableField({ label, value }: { label: string; value: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <label className="block">
      <span className={labelClass}>{label}</span>
      <span className="flex gap-2">
        <Input readOnly value={value} className="font-mono" />
        <button
          type="button"
          aria-label={`Copy ${label}`}
          onClick={() => {
            void navigator.clipboard.writeText(value).then(() => {
              setCopied(true);
              window.setTimeout(() => {
                setCopied(false);
              }, 1500);
            });
          }}
          className="flex size-9 shrink-0 cursor-pointer items-center justify-center rounded-[7px] border border-input text-meta transition-colors hover:bg-hover hover:text-foreground"
        >
          {copied ? (
            <Check className="size-3.5" />
          ) : (
            <Copy className="size-3.5" />
          )}
        </button>
      </span>
    </label>
  );
}

function IntegrationCard({
  provider,
  title,
  description,
  configured,
  detail,
  enabled,
  saving,
  status,
  onToggle,
  onSave,
  children,
}: {
  provider: Provider;
  title: string;
  description: string;
  configured: boolean;
  detail: string;
  enabled: boolean;
  saving: boolean;
  status: string | null;
  onToggle: (checked: boolean) => void;
  onSave: () => void;
  children: React.ReactNode;
}) {
  return (
    <div className="overflow-hidden rounded-[10px] border border-border bg-card dark:border-white/10">
      <div className="space-y-5 px-4 py-4">
        <div className="flex items-center gap-3">
          <span className="flex size-9 items-center justify-center rounded-[9px] border border-input bg-hover text-petrol">
            {provider === "telegram" ? (
              <Send className="size-4" />
            ) : (
              <MessageCircle className="size-4" />
            )}
          </span>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-1.5">
              <div className="text-[13px] font-semibold text-foreground">
                {title}
              </div>
              <TutorialButton provider={provider} />
            </div>
            <div className="text-[11.5px] text-meta">
              {configured ? detail : "Not configured"} · {description}
            </div>
          </div>
          <Switch
            checked={enabled}
            disabled={saving}
            onCheckedChange={onToggle}
            className="cursor-pointer data-[state=checked]:bg-petrol"
          />
        </div>
        {enabled && children}
      </div>
      {enabled && (
        <div className="flex items-center gap-3 border-t border-hairline px-4 py-3">
          <HeaderButton accent disabled={saving} onClick={onSave}>
            {saving ? "Saving…" : "Save changes"}
          </HeaderButton>
          {status && <span className="text-[12px] text-subtle">{status}</span>}
        </div>
      )}
    </div>
  );
}

export default function WorkspaceNotifications({ onForbidden }: Props) {
  const [slack, setSlack] = useState<SlackNotificationSettings | null>(null);
  const [telegram, setTelegram] = useState<TelegramNotificationSettings | null>(
    null,
  );
  const [discord, setDiscord] = useState<DiscordNotificationSettings | null>(
    null,
  );
  const [enabled, setEnabled] = useState<Record<Provider, boolean>>({
    slack: false,
    telegram: false,
    discord: false,
  });
  const [secrets, setSecrets] = useState({
    slackToken: "",
    slackSigning: "",
    telegramToken: "",
    discordToken: "",
    discordApplicationId: "",
    discordPublicKey: "",
  });
  const [saving, setSaving] = useState<Provider | null>(null);
  const [status, setStatus] = useState<Partial<Record<Provider, string>>>({});
  const [loadError, setLoadError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoadError(null);
    try {
      const [slackValue, telegramValue, discordValue] = await Promise.all([
        notificationsApi.getSlackSettings(),
        notificationsApi.getTelegramSettings(),
        notificationsApi.getDiscordSettings(),
      ]);
      setSlack(slackValue);
      setTelegram(telegramValue);
      setDiscord(discordValue);
      setEnabled({
        slack: slackValue.enabled,
        telegram: telegramValue.enabled,
        discord: discordValue.enabled,
      });
      setSecrets((current) => ({
        ...current,
        discordApplicationId: discordValue.applicationId ?? "",
      }));
    } catch (error: unknown) {
      if (isApiError(error) && error.status === 403) {
        onForbidden();
        return;
      }
      setLoadError(
        getApiErrorMessage(error, "Could not load integration settings."),
      );
    }
  }, [onForbidden]);

  useEffect(() => {
    void load();
  }, [load]);

  const fail = (provider: Provider, error: unknown) => {
    if (isApiError(error) && error.status === 403) onForbidden();
    setStatus((current) => ({
      ...current,
      [provider]: getApiErrorMessage(error, "Could not save integration."),
    }));
  };

  const toggle = async (provider: Provider, checked: boolean) => {
    const settings = { slack, telegram, discord }[provider];
    setEnabled((current) => ({ ...current, [provider]: checked }));
    setStatus((current) => ({ ...current, [provider]: "" }));
    if (checked && !settings?.isConfigured) return;
    setSaving(provider);
    try {
      if (provider === "slack") {
        setSlack(
          await notificationsApi.updateSlackSettings({ enabled: checked }),
        );
      } else if (provider === "telegram") {
        setTelegram(
          await notificationsApi.updateTelegramSettings({ enabled: checked }),
        );
      } else {
        setDiscord(
          await notificationsApi.updateDiscordSettings({ enabled: checked }),
        );
      }
    } catch (error: unknown) {
      setEnabled((current) => ({ ...current, [provider]: !checked }));
      fail(provider, error);
    } finally {
      setSaving(null);
    }
  };

  const saveSlack = async () => {
    setSaving("slack");
    try {
      const replacing =
        secrets.slackToken.trim() || secrets.slackSigning.trim();
      setSlack(
        await notificationsApi.updateSlackSettings({
          enabled: enabled.slack,
          ...(replacing
            ? {
                botToken: secrets.slackToken.trim(),
                signingSecret: secrets.slackSigning.trim(),
              }
            : {}),
        }),
      );
      setSecrets((current) => ({
        ...current,
        slackToken: "",
        slackSigning: "",
      }));
      setStatus((current) => ({ ...current, slack: "Saved." }));
    } catch (error: unknown) {
      fail("slack", error);
    } finally {
      setSaving(null);
    }
  };

  const saveTelegram = async () => {
    setSaving("telegram");
    try {
      setTelegram(
        await notificationsApi.updateTelegramSettings({
          enabled: enabled.telegram,
          ...(secrets.telegramToken.trim()
            ? { botToken: secrets.telegramToken.trim() }
            : {}),
        }),
      );
      setSecrets((current) => ({ ...current, telegramToken: "" }));
      setStatus((current) => ({ ...current, telegram: "Saved." }));
    } catch (error: unknown) {
      fail("telegram", error);
      await load();
    } finally {
      setSaving(null);
    }
  };

  const saveDiscord = async () => {
    setSaving("discord");
    try {
      setDiscord(
        await notificationsApi.updateDiscordSettings({
          enabled: enabled.discord,
          ...(secrets.discordToken.trim()
            ? { botToken: secrets.discordToken.trim() }
            : {}),
          ...(secrets.discordApplicationId.trim()
            ? { applicationId: secrets.discordApplicationId.trim() }
            : {}),
          ...(secrets.discordPublicKey.trim()
            ? { publicKey: secrets.discordPublicKey.trim() }
            : {}),
        }),
      );
      setSecrets((current) => ({
        ...current,
        discordToken: "",
        discordPublicKey: "",
      }));
      setStatus((current) => ({ ...current, discord: "Saved." }));
    } catch (error: unknown) {
      fail("discord", error);
      await load();
    } finally {
      setSaving(null);
    }
  };

  if (!slack || !telegram || !discord) {
    if (loadError) {
      return (
        <div className="rounded-[10px] border border-destructive/25 bg-destructive/5 p-5">
          <p className="text-[13px] text-destructive">{loadError}</p>
          <button
            type="button"
            onClick={() => {
              void load();
            }}
            className="mt-3 cursor-pointer rounded-[7px] border border-input bg-card px-3 py-1.5 text-[12px] font-semibold"
          >
            Retry
          </button>
        </div>
      );
    }
    return <div className="h-64 animate-pulse rounded-[10px] border bg-card" />;
  }

  const secretInput = (
    label: string,
    value: string,
    onChange: (value: string) => void,
    placeholder = "Leave blank to keep current",
  ) => (
    <label className="block">
      <span className={labelClass}>{label}</span>
      <Input
        type="password"
        value={value}
        onChange={(event) => {
          onChange(event.target.value);
        }}
        placeholder={placeholder}
      />
    </label>
  );

  return (
    <div>
      <div className="mb-1.5 flex items-baseline gap-2.5">
        <span className="text-[10.5px] font-semibold text-subtle">
          Messaging
        </span>
        <span className="text-[10.5px] text-meta">admin</span>
      </div>
      <p className="mb-3.5 max-w-[680px] text-[13px] leading-[1.55] text-subtle">
        Let workspace members run agents from Slack, Telegram or Discord.
      </p>
      <div className="space-y-3">
        <IntegrationCard
          provider="slack"
          title="Slack"
          description="assistant threads and messages"
          configured={slack.isConfigured}
          detail={`Token ending in ${slack.botTokenLast4}`}
          enabled={enabled.slack}
          saving={saving === "slack"}
          status={status.slack ?? null}
          onToggle={(checked) => {
            void toggle("slack", checked);
          }}
          onSave={() => {
            void saveSlack();
          }}
        >
          {secretInput(
            "Bot token",
            secrets.slackToken,
            (value) => {
              setSecrets((current) => ({ ...current, slackToken: value }));
            },
            "xoxb-…",
          )}
          {secretInput("Signing secret", secrets.slackSigning, (value) => {
            setSecrets((current) => ({ ...current, slackSigning: value }));
          })}
          <CopyableField label="Events request URL" value={slack.eventsUrl} />
          <CopyableField
            label="Interactions request URL"
            value={slack.interactionsUrl}
          />
        </IntegrationCard>

        <IntegrationCard
          provider="telegram"
          title="Telegram"
          description="bot chats and inline approvals"
          configured={telegram.isConfigured}
          detail={`@${telegram.botUsername ?? "bot"}`}
          enabled={enabled.telegram}
          saving={saving === "telegram"}
          status={status.telegram ?? null}
          onToggle={(checked) => {
            void toggle("telegram", checked);
          }}
          onSave={() => {
            void saveTelegram();
          }}
        >
          {secretInput("Bot token", secrets.telegramToken, (value) => {
            setSecrets((current) => ({ ...current, telegramToken: value }));
          })}
          <CopyableField label="Webhook URL" value={telegram.webhookUrl} />
        </IntegrationCard>

        <IntegrationCard
          provider="discord"
          title="Discord"
          description="slash commands and component approvals"
          configured={discord.isConfigured}
          detail={discord.botUsername ?? "Configured"}
          enabled={enabled.discord}
          saving={saving === "discord"}
          status={status.discord ?? null}
          onToggle={(checked) => {
            void toggle("discord", checked);
          }}
          onSave={() => {
            void saveDiscord();
          }}
        >
          <label className="block">
            <span className={labelClass}>Application ID</span>
            <Input
              value={secrets.discordApplicationId}
              onChange={(event) => {
                setSecrets((current) => ({
                  ...current,
                  discordApplicationId: event.target.value,
                }));
              }}
            />
          </label>
          {secretInput("Public key", secrets.discordPublicKey, (value) => {
            setSecrets((current) => ({ ...current, discordPublicKey: value }));
          })}
          {secretInput("Bot token", secrets.discordToken, (value) => {
            setSecrets((current) => ({ ...current, discordToken: value }));
          })}
          <CopyableField
            label="Interactions Endpoint URL"
            value={discord.interactionsUrl}
          />
          {discord.installUrl && (
            <a
              href={discord.installUrl}
              target="_blank"
              rel="noreferrer"
              className="inline-flex text-[12.5px] font-semibold text-petrol hover:underline"
            >
              Install bot on Discord
            </a>
          )}
        </IntegrationCard>
      </div>
    </div>
  );
}
