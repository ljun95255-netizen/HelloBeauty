import Taro, { useDidShow } from "@tarojs/taro";
import { Button, Image, Text, View } from "@tarojs/components";
import { useCallback, useMemo, useRef, useState } from "react";

import { spacing } from "@hellobeauty/design-tokens";

import { miniEditorialStyles as styles, stack } from "../../utils/editorial";
import { getLocalImageSrc, useLocalImageMap } from "../../utils/use-local-image";
import { RETOUCH_CATEGORIES, type RetouchParam } from "../../utils/retouch-categories";
import RetouchSlider from "../../components/retouch-slider";
import {
  type SessionPhoto, clearSessionScopedState, listSessionPhotos, readCurrentSession, readCustomerToken,
  processTargetedRetouchV2,
  writeCompletedResults,
} from "../../utils/api";

type ParamValues = Record<string, number>;

export default function RetouchPage() {
  const [photo, setPhoto] = useState<SessionPhoto | null>(null);
  const [selectedPhotos, setSelectedPhotos] = useState<SessionPhoto[]>([]);
  const [paramValues, setParamValues] = useState<ParamValues>(() => {
    const init: ParamValues = {};
    for (const cat of RETOUCH_CATEGORIES) {
      for (const p of cat.params) init[p.key] = p.defaultValue;
    }
    return init;
  });
  const [activeCategory, setActiveCategory] = useState("face");
  const [processing, setProcessing] = useState(false);
  const [resultImage, setResultImage] = useState<string | null>(null);
  const [showOriginal, setShowOriginal] = useState(false);
  const [error, setError] = useState("");
  const previewImageMap = useLocalImageMap(photo ? [photo.previewUrl] : []);
  const resultImageMap = useLocalImageMap(resultImage ? [resultImage] : []);

  useDidShow(() => {
    const token = readCustomerToken();
    const session = readCurrentSession();
    if (!token || !session) {
      void Taro.redirectTo({ url: "/pages/login/index" });
      return;
    }
    listSessionPhotos(token, session.id)
      .then((p) => {
        const selected = p.filter((ph) => ph.selected);
        setSelectedPhotos(selected);
        if (selected.length > 0) setPhoto(selected[0]);
        else if (p.length > 0) setPhoto(p[0]);
      })
      .catch((nextError) => {
        if (nextError instanceof Error && /Session not found|status 404|404 Not Found/i.test(nextError.message)) {
          clearSessionScopedState();
          setPhoto(null);
          setError("当前场次已失效，请重新预约后再精修。");
          return;
        }
        setError(nextError instanceof Error ? nextError.message : "照片加载失败");
      });
  });

  const updateParam = useCallback((key: string, value: number) => {
    setParamValues((prev) => ({ ...prev, [key]: value }));
  }, []);

  const resetAll = () => {
    const init: ParamValues = {};
    for (const cat of RETOUCH_CATEGORIES) {
      for (const p of cat.params) init[p.key] = p.defaultValue;
    }
    setParamValues(init);
    setResultImage(null);
  };

  const handleProcess = async () => {
    const token = readCustomerToken();
    const photosToProcess = selectedPhotos.length > 0 ? selectedPhotos : photo ? [photo] : [];
    if (!token || photosToProcess.length === 0) return;
    setProcessing(true);
    setError("");
    try {
      const completedResults = await Promise.all(
        photosToProcess.map(async (item) => {
          const result = await processTargetedRetouchV2(token, item.id, paramValues);
          return {
            photoId: item.id,
            filename: item.filename,
            previewUrl: item.previewUrl,
            resultImageUrl: result.image,
            mode: "retouch" as const,
          };
        }),
      );
      setResultImage(completedResults[0]?.resultImageUrl ?? null);
      writeCompletedResults(completedResults);
      void Taro.showToast({ title: `精修完成 ${completedResults.length} 张`, icon: "success" });
    } catch (e) {
      setError(e instanceof Error ? e.message : "精修失败");
    } finally {
      setProcessing(false);
    }
  };

  const activeCat = useMemo(
    () => RETOUCH_CATEGORIES.find((c) => c.id === activeCategory) ?? RETOUCH_CATEGORIES[0],
    [activeCategory],
  );

  const src = photo ? getLocalImageSrc(photo.previewUrl, previewImageMap) : "";
  const resultSrc = resultImage ? getLocalImageSrc(resultImage, resultImageMap) : "";
  const displaySrc = (showOriginal && photo) ? src : (resultSrc || src);

  return (
    <View className="page" style={{ ...styles.page, paddingBottom: "calc(200px + env(safe-area-inset-bottom))" }}>
      {/* Header */}
      <View style={{ ...styles.header, marginBottom: spacing.sm }}>
        <View style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <Text style={styles.title}>针对性精修</Text>
          <View style={{ display: "flex", gap: spacing.sm }}>
            <Button onClick={resetAll} style={{ ...styles.tertiaryButton, minHeight: "44px", height: "44px", padding: "0 16px", margin: 0 }}>
              <Text style={{ fontSize: "12px" }}>重置</Text>
            </Button>
          </View>
        </View>
      </View>

      {/* Image preview */}
      <View
        style={{
          width: "100%", aspectRatio: "3/4",
          maxHeight: "420px", position: "relative",
          overflow: "hidden", border: `1px solid ${styles.portraitThumbFrame?.border ?? "rgba(28,28,28,0.14)"}`,
          backgroundColor: "rgba(28,28,28,0.04)",
          marginBottom: spacing.sm,
        }}
        onTouchStart={() => setShowOriginal(true)}
        onTouchEnd={() => setShowOriginal(false)}
        onTouchCancel={() => setShowOriginal(false)}
      >
        {displaySrc ? (
          <Image src={displaySrc} mode="aspectFill" style={{ width: "100%", height: "100%" }} />
        ) : null}
        <View style={{
          position: "absolute", bottom: "8px", left: "50%", transform: "translateX(-50%)",
          backgroundColor: "rgba(0,0,0,0.5)", borderRadius: "999px", padding: "4px 12px",
        }}>
          <Text style={{ fontSize: "11px", color: "#fff", letterSpacing: "0.05em" }}>
            {showOriginal ? "原图" : resultImage ? "精修后" : "原图"}
          </Text>
        </View>
        {resultImage && (
          <Text style={{
            position: "absolute", bottom: "8px", left: "12px",
            fontSize: "10px", color: "rgba(255,255,255,0.6)",
          }}>
            按住查看原图对比
          </Text>
        )}
      </View>

      {/* Category tabs */}
      <View style={{
        display: "flex", gap: "4px", marginBottom: spacing.sm,
        overflowX: "auto", whiteSpace: "nowrap",
        WebkitOverflowScrolling: "touch",
        padding: "4px 0",
      }}>
        {RETOUCH_CATEGORIES.map((cat) => {
          const active = cat.id === activeCategory;
          const hasChanges = cat.params.some((p) => paramValues[p.key] !== p.defaultValue);
          return (
            <Button
              key={cat.id}
              onClick={() => setActiveCategory(cat.id)}
              style={{
                display: "inline-flex", alignItems: "center", gap: "4px",
                minHeight: "44px",
                height: "44px",
                padding: "0 16px",
                borderRadius: "999px",
                backgroundColor: active ? "#1C1C1C" : "rgba(28,28,28,0.06)",
                flexShrink: 0,
                position: "relative",
                margin: 0,
              }}
            >
              <Text style={{ fontSize: "12px", color: active ? "#F9F8F6" : "#1C1C1C" }}>
                {cat.icon} {cat.label}
              </Text>
              {hasChanges && (
                <View style={{
                  position: "absolute", top: "-2px", right: "-2px",
                  width: "6px", height: "6px", borderRadius: "999px",
                  backgroundColor: active ? "#F9F8F6" : "#1C1C1C",
                }} />
              )}
            </Button>
          );
        })}
      </View>

      {/* Parameter sliders */}
      <View style={{
        ...styles.panel, ...stack("0px"),
        maxHeight: "280px", overflowY: "auto",
        WebkitOverflowScrolling: "touch",
      }}>
        {activeCat.params.map((param) => (
          <RetouchSlider
            key={param.key}
            param={param}
            value={paramValues[param.key] ?? param.defaultValue}
            onChange={updateParam}
          />
        ))}
      </View>

      {/* Process button */}
      <View style={{ position: "fixed", bottom: 0, left: 0, right: 0, padding: `${spacing.md} ${spacing.md} calc(${spacing.md} + env(safe-area-inset-bottom))`, backgroundColor: "#F9F8F6", borderTop: "1px solid rgba(28,28,28,0.08)", zIndex: 100 }}>
        {error ? <Text style={{ ...styles.body, color: "#8A5A5F", marginBottom: spacing.xs }}>{error}</Text> : null}
        <Button
          disabled={processing || !photo}
          onClick={handleProcess}
          style={{ ...styles.primaryButton, width: "100%" }}
        >
          {processing ? "精修中..." : "开始精修"}
        </Button>
        {resultImage ? (
          <Button
            disabled={processing}
            onClick={() => void Taro.navigateTo({ url: "/pages/complete/index" })}
            style={{ ...styles.secondaryButton, width: "100%", marginTop: spacing.sm }}
          >
            导出结果
          </Button>
        ) : null}
      </View>
    </View>
  );
}
