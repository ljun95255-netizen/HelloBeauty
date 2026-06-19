import Taro, { useDidShow } from "@tarojs/taro";
import { Button, Image, Text, View } from "@tarojs/components";
import { useMemo, useState } from "react";

import { spacing } from "@hellobeauty/design-tokens";
import { editorialMiniCopy, editorialStudioModes } from "@hellobeauty/domain";
import type { EditJob, EditMode } from "@hellobeauty/domain";

import { miniEditorialStyles as styles, stack } from "../../utils/editorial";
import { getLocalImageSrc, useLocalImageMap } from "../../utils/use-local-image";
import {
  type SessionPhoto,
  createEditJob,
  initializeJesrRecipe,
  listSessionPhotos,
  pollEditJob,
  readCurrentSession,
  readCustomerToken,
  renderWithRecipe,
  selectCreativeStyle,
  writeCompletedResults,
  smartOptimize,
  getPreferenceProfile,
} from "../../utils/api";

const modeOptions = editorialStudioModes.map((mode) => ({
  id: mode.id as EditMode,
  label: mode.label,
  description: mode.description,
}));
const CREATIVE_STYLE_PRESETS = [
  { id: "fresh_japanese", label: "清新日系" },
  { id: "retro_hongkong", label: "复古港风" },
  { id: "clear_korean", label: "清透韩系" },
  { id: "lazy_french", label: "法式慵懒" },
  { id: "american_hotgirl", label: "美式辣妹" },
] as const;

export default function EditPage() {
  const [selectedMode, setSelectedMode] = useState<EditMode>("beauty");
  const [photos, setPhotos] = useState<SessionPhoto[]>([]);
  const [selectedPhotoId, setSelectedPhotoId] = useState<string | null>(null);
  const [processing, setProcessing] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState("");
  const [preferenceSet, setPreferenceSet] = useState(false);
  const [smartResult, setSmartResult] = useState<string | null>(null);
  const [creativePreset, setCreativePreset] = useState<(typeof CREATIVE_STYLE_PRESETS)[number]["id"]>("fresh_japanese");
  const previewImageMap = useLocalImageMap(photos.map((photo) => photo.previewUrl));
  const smartResultMap = useLocalImageMap(smartResult ? [smartResult] : []);

  const loadPhotos = async () => {
    const token = readCustomerToken();
    const session = readCurrentSession();
    if (!token || !session) {
      void Taro.redirectTo({ url: "/pages/login/index" });
      return;
    }

    try {
      const nextPhotos = await listSessionPhotos(token, session.id);
      const selectedOnes = nextPhotos.filter((photo) => photo.selected);
      setPhotos(selectedOnes);
      if (
        selectedOnes.length > 0 &&
        (!selectedPhotoId || !selectedOnes.some((photo) => photo.id === selectedPhotoId))
      ) {
        setSelectedPhotoId(selectedOnes[0].id);
      }

      const pref = await getPreferenceProfile(token, session.id);
      setPreferenceSet(pref?.is_set ?? false);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "照片加载失败");
    }
  };

  const handleStartEdit = async (modeOverride?: EditMode) => {
    const activeMode = modeOverride ?? selectedMode;
    const selectedPhotos = photos.filter((photo) => photo.selected);
    if (selectedPhotos.length === 0) {
      setError("请先在上一页选择至少一张照片");
      return;
    }

    if (activeMode === "retouch") {
      void Taro.navigateTo({ url: "/pages/retouch/index" });
      return;
    }

    const token = readCustomerToken();
    const session = readCurrentSession();
    if (!token) {
      void Taro.redirectTo({ url: "/pages/login/index" });
      return;
    }
    if (!session) {
      void Taro.redirectTo({ url: "/pages/login/index" });
      return;
    }

    setProcessing(true);
    setProgress(0);
    setError("");
    let progressInterval: ReturnType<typeof setInterval> | null = null;

    try {
      progressInterval = setInterval(() => {
        setProgress((currentProgress) => Math.min(currentProgress + 6, 24));
      }, 500);

      let createdJobs: EditJob[];
      if (activeMode === "filter") {
        try {
          await initializeJesrRecipe(token, session.id, selectedPhotos[0].id);
        } catch (nextError) {
          const message = nextError instanceof Error ? nextError.message : "";
          if (!message.includes("JESR recipe already initialized")) {
            throw nextError;
          }
        }
        await selectCreativeStyle(token, session.id, creativePreset);
        createdJobs = await Promise.all(
          selectedPhotos.map((photo) => renderWithRecipe(token, session.id, photo.id, "auto")),
        );
      } else {
        createdJobs = await Promise.all(
          selectedPhotos.map((photo) => createEditJob(token, photo.id, activeMode)),
        );
      }
      let completedCount = 0;

      const completedResults = await Promise.all(
        createdJobs.map(async (job, index) => {
          const completedJob = await pollEditJob(token, job.id);
          const photo = selectedPhotos[index];

          completedCount += 1;
          setProgress((currentProgress) =>
            Math.max(
              currentProgress,
              Math.min(96, 24 + Math.round((completedCount / createdJobs.length) * 72)),
            ),
          );

          if (!completedJob.resultImageUrl) {
            throw new Error("处理结果缺失，请稍后重试");
          }

          return {
            photoId: photo.id,
            filename: photo.filename,
            previewUrl: photo.previewUrl,
            resultImageUrl: completedJob.resultImageUrl,
            mode: completedJob.mode,
          };
        }),
      );

      if (progressInterval) {
        clearInterval(progressInterval);
      }
      setProgress(100);
      writeCompletedResults(completedResults);

      void Taro.showToast({ title: "精修完成", icon: "success" });
      setTimeout(() => {
        void Taro.navigateTo({ url: "/pages/complete/index" });
      }, 800);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "精修失败");
    } finally {
      if (progressInterval) {
        clearInterval(progressInterval);
      }
      setProcessing(false);
    }
  };

  const handleSmartOptimize = async () => {
    const token = readCustomerToken();
    const selectedPhotos = photos.filter((photo) => photo.selected);
    if (!token || selectedPhotos.length === 0) return;

    setProcessing(true);
    setError("");
    try {
      const completedResults = await Promise.all(
        selectedPhotos.map(async (photo) => {
          const result = await smartOptimize(token, photo.id);
          return {
            photoId: photo.id,
            filename: photo.filename,
            previewUrl: photo.previewUrl,
            resultImageUrl: result.image,
            mode: "beauty" as EditMode,
          };
        }),
      );
      writeCompletedResults(completedResults);
      setSmartResult(completedResults[0]?.resultImageUrl ?? null);
      void Taro.showToast({ title: "智能优化完成", icon: "success" });
      setTimeout(() => {
        void Taro.navigateTo({ url: "/pages/complete/index" });
      }, 600);
    } catch (e) {
      setError(e instanceof Error ? e.message : "智能优化失败");
    } finally {
      setProcessing(false);
    }
  };

  const handleGoPreference = () => {
    void Taro.navigateTo({ url: "/pages/preference/index" });
  };

  useDidShow(() => {
    void loadPhotos();
  });

  const currentPhoto = useMemo(
    () => photos.find((photo) => photo.id === selectedPhotoId) ?? photos[0] ?? null,
    [photos, selectedPhotoId],
  );

  return (
    <View className="page" style={styles.page}>
      <View style={styles.header}>
        <Text style={styles.eyebrow}>Edit</Text>
        <Text style={styles.title}>{editorialMiniCopy.edit.title}</Text>
        <Text style={styles.body}>{editorialMiniCopy.edit.body}</Text>
      </View>

      <View style={{ ...styles.panel, ...stack(spacing.sm) }}>
        <Text style={styles.label}>修图模式</Text>
        {modeOptions.map((mode) => (
          <View
            key={mode.id}
            onClick={() => setSelectedMode(mode.id)}
            style={{
              ...styles.softPanel,
              border: `1px solid ${selectedMode === mode.id ? "#1C1C1C" : "rgba(28, 28, 28, 0.14)"}`,
              backgroundColor: selectedMode === mode.id ? "#1C1C1C" : "#FFFDFA",
            }}
          >
            <Text style={{ color: selectedMode === mode.id ? "#F9F8F6" : "#1C1C1C" }}>{mode.label}</Text>
            <Text style={{ ...styles.body, color: selectedMode === mode.id ? "rgba(249, 248, 246, 0.72)" : "#6b7280" }}>
              {mode.description}
            </Text>
          </View>
        ))}
        {selectedMode === "filter" ? (
          <View style={styles.segmentedControl}>
            {CREATIVE_STYLE_PRESETS.map((preset) => (
              <View
                key={preset.id}
                onClick={() => setCreativePreset(preset.id)}
                style={creativePreset === preset.id ? styles.segmentItemActive : styles.segmentItem}
              >
                <Text>{preset.label}</Text>
              </View>
            ))}
          </View>
        ) : null}
      </View>

      <View style={{ ...styles.panel, ...stack(spacing.sm) }}>
        <Text style={styles.label}>一键智能优化</Text>
        {preferenceSet ? (
          <>
            <Text style={styles.body}>已基于你的风格爱好，点击下方按钮快速优化</Text>
            <Button
              disabled={processing || !currentPhoto}
              onClick={handleSmartOptimize}
              style={styles.primaryButton}
            >
              {processing ? "处理中..." : "一键智能优化"}
            </Button>
            {smartResult ? (
              <View style={{ ...styles.portraitPreviewWrap, marginTop: spacing.xs }}>
                <View style={styles.portraitPreviewFrame}>
                <Image
                  src={getLocalImageSrc(smartResult, smartResultMap)}
                  mode="aspectFill"
                  style={styles.portraitPreviewImage}
                />
                </View>
              </View>
            ) : null}
          </>
        ) : (
          <>
            <Text style={styles.body}>
              你还没有设置风格爱好。可以先用 25 张风格照片或心仪照片记录风格爱好，也可以直接使用基础自适应优化。
            </Text>
            <View style={styles.actionButtonRow}>
              <Button onClick={handleGoPreference} style={{ ...styles.secondaryButton, width: "100%" }}>
                设置风格爱好
              </Button>
              <Button onClick={() => void handleStartEdit("beauty")} style={{ ...styles.primaryButton, width: "100%" }}>
                基础优化
              </Button>
            </View>
          </>
        )}
      </View>

      <View style={{ ...styles.panel, ...stack(spacing.sm) }}>
        <Text style={styles.label}>照片预览</Text>
        <View style={styles.portraitThumbRail}>
          {photos.map((photo) => (
            <View
              key={photo.id}
              onClick={() => setSelectedPhotoId(photo.id)}
              style={{
                ...styles.portraitThumbFrame,
                border: `1px solid ${selectedPhotoId === photo.id ? "#1C1C1C" : "rgba(28, 28, 28, 0.14)"}`,
              }}
            >
              <Image
                src={getLocalImageSrc(photo.previewUrl, previewImageMap)}
                mode="aspectFill"
                style={styles.portraitThumbImage}
              />
            </View>
          ))}
        </View>

        {currentPhoto ? (
          <View style={{ ...styles.portraitPreviewWrap, marginTop: spacing.xs }}>
            <View style={styles.portraitPreviewFrame}>
              <Image
                src={getLocalImageSrc(currentPhoto.previewUrl, previewImageMap)}
                mode="aspectFill"
                style={styles.portraitPreviewImage}
              />
            </View>
          </View>
        ) : null}
      </View>

      {processing ? (
        <View style={{ ...styles.panel, ...stack(spacing.xs) }}>
          <Text style={styles.label}>处理进度</Text>
          <Text style={styles.body}>{progress}%</Text>
          <View style={{ height: "6px", backgroundColor: "rgba(28, 28, 28, 0.08)" }}>
            <View
              style={{
                width: `${progress}%`,
                height: "100%",
                backgroundColor: "#1C1C1C",
                transition: "width 300ms",
              }}
            />
          </View>
        </View>
      ) : null}

      {error ? <Text style={{ ...styles.body, color: "#8A5A5F" }}>{error}</Text> : null}

      <Button
        disabled={processing || photos.length === 0}
        onClick={() => void handleStartEdit()}
        style={styles.primaryButton}
      >
        {processing ? "精修中" : `开始精修${photos.length ? `（${photos.length} 张）` : ""}`}
      </Button>
    </View>
  );
}
