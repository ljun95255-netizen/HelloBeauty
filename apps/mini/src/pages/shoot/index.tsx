import Taro, { useDidShow } from "@tarojs/taro";
import { Button, Image, Text, View } from "@tarojs/components";
import { useEffect, useMemo, useRef, useState } from "react";

import { spacing } from "@hellobeauty/design-tokens";
import { DEFAULT_STORE_ID } from "@hellobeauty/domain";

import { miniEditorialStyles as styles, stack } from "../../utils/editorial";
import { getLocalImageSrc, useLocalImageMap } from "../../utils/use-local-image";
import {
  type CustomerSession,
  type EntryPreference,
  type SessionPhoto,
  clearSessionScopedState,
  listSessionPhotos,
  readCurrentSession,
  readCustomerToken,
  readEntryPreference,
  readSessionCode,
  setReferencePhotoPreference,
  uploadIngressPhoto,
  writeEntryPreference,
} from "../../utils/api";

type CaptureState = "idle" | "countdown" | "shooting" | "ended";

function loginUrl(next: string): string {
  return `/pages/login/index?next=${encodeURIComponent(next)}`;
}

export default function ShootPage() {
  const [session, setSession] = useState<CustomerSession | null>(readCurrentSession());
  const [entryPreference, setEntryPreference] = useState<EntryPreference | null>(readEntryPreference());
  const [photos, setPhotos] = useState<SessionPhoto[]>([]);
  const [captureState, setCaptureState] = useState<CaptureState>("idle");
  const [countdown, setCountdown] = useState(3);
  const [loading, setLoading] = useState(false);
  const [referenceSyncing, setReferenceSyncing] = useState(false);
  const [error, setError] = useState("");

  const token = readCustomerToken();
  const sessionCode = readSessionCode();
  const recentPhotos = useMemo(() => [...photos].reverse(), [photos]);
  const latestPhoto = recentPhotos[0] ?? null;
  const previewImageMap = useLocalImageMap(recentPhotos.map((photo) => photo.previewUrl));
  const refreshInFlightRef = useRef(false);

  const refreshPhotos = async (sessionId?: string) => {
    const activeSessionId = sessionId ?? session?.id;
    const activeToken = readCustomerToken();
    if (!activeSessionId || !activeToken) {
      return;
    }
    if (refreshInFlightRef.current) {
      return;
    }

    refreshInFlightRef.current = true;
    try {
      const nextPhotos = await listSessionPhotos(activeToken, activeSessionId);
      setPhotos(nextPhotos);
    } catch (nextError) {
      if (nextError instanceof Error && /Session not found|status 404|404 Not Found/i.test(nextError.message)) {
        clearSessionScopedState();
        setSession(null);
        setPhotos([]);
        setError("当前场次已失效，请重新预约后再拍摄。");
        return;
      }
      setError(nextError instanceof Error ? nextError.message : "照片加载失败");
    } finally {
      refreshInFlightRef.current = false;
    }
  };

  const ensureSession = async () => {
    const activeToken = readCustomerToken();
    if (!activeToken) {
      void Taro.redirectTo({ url: loginUrl("/pages/shoot/index") });
      return null;
    }

    if (session) {
      return session;
    }

    setError("请先预约场次");
    void Taro.showModal({
      title: "请先预约",
      content: "预约成功后即可开始拍摄。",
      confirmText: "去预约",
      showCancel: false,
      success: () => {
        void Taro.redirectTo({ url: "/pages/swipe/index" });
      },
    });
    return null;
  };

  const syncPreferredReference = async (activeSession: CustomerSession) => {
    const activeToken = readCustomerToken();
    const pendingFiles = entryPreference?.mode === "upload" ? entryPreference.uploadedFiles : [];
    if (!activeToken || pendingFiles.length === 0) {
      return;
    }

    setReferenceSyncing(true);
    setError("");
    try {
      const uploadedPhotos = [];
      for (const filePath of pendingFiles) {
        uploadedPhotos.push(await uploadIngressPhoto(activeToken, DEFAULT_STORE_ID, activeSession.id, filePath));
      }
      await setReferencePhotoPreference(
        activeToken,
        activeSession.id,
        uploadedPhotos.map((photo) => photo.id),
      );
      const nextPreference = {
        mode: "upload" as const,
        uploadedFiles: [],
        likedSampleIds: entryPreference?.likedSampleIds ?? [],
        seedChoices: entryPreference?.seedChoices,
        referencePhotoIds: uploadedPhotos.map((photo) => photo.id),
      };
      setEntryPreference(nextPreference);
      writeEntryPreference(nextPreference);
      await refreshPhotos(activeSession.id);
      void Taro.showToast({ title: "心仪照片已同步", icon: "success" });
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "心仪照片同步失败");
      throw nextError;
    } finally {
      setReferenceSyncing(false);
    }
  };

  const handleStartShooting = async () => {
    const activeSession = await ensureSession();
    if (!activeSession) {
      return;
    }

    if (entryPreference?.mode === "upload" && entryPreference.uploadedFiles.length > 0) {
      await syncPreferredReference(activeSession);
    }

    setCountdown(3);
    setCaptureState("countdown");
  };

  const handleUpload = async () => {
    const activeSession = await ensureSession();
    const activeToken = readCustomerToken();
    if (!activeSession) {
      return;
    }
    if (!activeToken) {
      void Taro.redirectTo({ url: loginUrl("/pages/shoot/index") });
      return;
    }

    setLoading(true);
    setError("");
    try {
      const pickResult = await Taro.chooseImage({
        count: 9,
        sourceType: ["album", "camera"],
      });
      for (const filePath of pickResult.tempFilePaths ?? []) {
        await uploadIngressPhoto(activeToken, DEFAULT_STORE_ID, activeSession.id, filePath);
      }
      await refreshPhotos(activeSession.id);
      void Taro.showToast({ title: "已接收照片", icon: "success" });
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "上传失败");
    } finally {
      setLoading(false);
    }
  };

  useDidShow(() => {
    if (!readCustomerToken()) {
      void Taro.redirectTo({ url: loginUrl("/pages/shoot/index") });
      return;
    }

    setEntryPreference(readEntryPreference());
    setSession(readCurrentSession());
    void refreshPhotos();
  });

  useEffect(() => {
    if (captureState !== "countdown") {
      return;
    }

    const timer = setInterval(() => {
      setCountdown((current) => {
        if (current <= 1) {
          clearInterval(timer);
          setCaptureState("shooting");
          return 0;
        }
        return current - 1;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [captureState]);

  useEffect(() => {
    if (captureState !== "shooting" || !session?.id || !token) {
      return;
    }

    const timer = setInterval(() => {
      void refreshPhotos(session.id);
    }, 3500);

    return () => clearInterval(timer);
  }, [captureState, session?.id, token]);

  const stageTitle =
    captureState === "countdown"
      ? String(countdown)
      : captureState === "shooting"
        ? "正在拍摄中"
        : captureState === "ended"
          ? "拍摄结束"
          : "准备开启拍摄";

  const stageBody =
    captureState === "shooting"
      ? "手机补拍或无线传输的照片会进入这个场次，最新一张会显示在中间。"
      : captureState === "ended"
        ? "现在可以进入选片，选择原图导出或进入美颜精修。"
        : "点击开启拍摄后自动创建场次文件，文件名格式为 001_手机号__YYYYMMDD_HHMM。";

  return (
    <View className="page" style={styles.page}>
      <View style={styles.header}>
        <Text style={styles.eyebrow}>Live Session</Text>
        <Text style={styles.title}>开启拍摄</Text>
        <Text style={styles.body}>场次号 {sessionCode} 将用于同组成员查看、手机上传和店内取片。</Text>
      </View>

      <View style={{ ...styles.sessionStrip, marginBottom: spacing.md }}>
        <View>
          <Text style={styles.microCaption}>Session</Text>
          <Text style={styles.deckText}>
            {session ? `已创建 · ${photos.length} 张照片` : "尚未创建 · 点击后自动生成"}
          </Text>
        </View>
        <Button loading={loading || referenceSyncing} onClick={handleStartShooting} style={styles.primaryButton}>
          {captureState === "shooting" ? "重新倒计时" : "开启拍摄"}
        </Button>
      </View>

      {entryPreference?.mode === "upload" ? (
        <View style={{ ...styles.parallaxBand, marginBottom: spacing.md }}>
          <Text style={styles.microCaption}>Preferred reference</Text>
          <Text style={styles.deckText}>
            {entryPreference.uploadedFiles.length > 0
              ? `有 ${entryPreference.uploadedFiles.length} 张心仪照片待同步，开始拍摄前会和风格爱好一起使用。`
              : "心仪照片已同步，后续一键智能优化会优先读取风格爱好。"}
          </Text>
        </View>
      ) : null}

      <View style={{ ...styles.liveStage, marginBottom: spacing.md }}>
        <View style={styles.liveStatusCard}>
          {latestPhoto && captureState !== "countdown" ? (
            <View style={styles.portraitPreviewFrame}>
              <Image
                src={getLocalImageSrc(latestPhoto.previewUrl, previewImageMap)}
                mode="aspectFill"
                style={styles.portraitPreviewImage}
              />
            </View>
          ) : (
            <Text style={captureState === "countdown" ? styles.countdownText : styles.optionTitleInverse}>
              {stageTitle}
            </Text>
          )}
          {latestPhoto && captureState !== "countdown" ? (
            <Text style={{ ...styles.microCaptionInverse }}>
              {captureState === "ended" ? "最后同步" : "最新同步"} · {latestPhoto.capturedAt}
            </Text>
          ) : null}
          <Text style={{ ...styles.body, color: "rgba(248, 250, 252, 0.78)", textAlign: "center" }}>
            {stageBody}
          </Text>
        </View>
      </View>

      <View style={{ ...styles.actionButtonRow, marginBottom: spacing.md }}>
        <Button loading={loading} disabled={!session && loading} onClick={handleUpload} style={{ ...styles.secondaryButton, width: "100%" }}>
          手机补拍/上传
        </Button>
        <Button
          disabled={!session}
          onClick={() => setCaptureState("ended")}
          style={{ ...styles.secondaryButton, width: "100%" }}
        >
          结束拍摄
        </Button>
      </View>

      <Button
        disabled={photos.length === 0}
        onClick={() => void Taro.navigateTo({ url: "/pages/album/index" })}
        style={{ ...styles.primaryButton, width: "100%", marginBottom: spacing.md }}
      >
        进入选片
      </Button>

      {error ? <Text style={{ ...styles.body, color: "#8A5A5F" }}>{error}</Text> : null}

      <View style={stack(spacing.sm)}>
        <View style={styles.utilityRow}>
          <Text style={styles.label}>实时照片卡片（{photos.length}）</Text>
          <Text style={styles.body}>左右滑动查看</Text>
        </View>
        {recentPhotos.length === 0 ? (
          <View style={styles.softPanel}>
            <Text style={styles.body}>暂未收到照片。当前版本以手机补拍/上传模拟无线传输，后续接相机后可直接刷新最新照片。</Text>
          </View>
        ) : (
          <View style={styles.liveRail}>
            {recentPhotos.map((photo) => (
              <View key={photo.id} style={styles.liveRailCard}>
                <View style={styles.portraitPreviewFrame}>
                  <Image
                    src={getLocalImageSrc(photo.previewUrl, previewImageMap)}
                    mode="aspectFill"
                    style={styles.portraitPreviewImage}
                  />
                </View>
                <Text style={styles.previewMetaText}>{photo.capturedAt}</Text>
              </View>
            ))}
          </View>
        )}
      </View>
    </View>
  );
}
