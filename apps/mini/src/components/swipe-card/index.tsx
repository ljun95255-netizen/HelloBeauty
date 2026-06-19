import Taro from "@tarojs/taro";
import { Image, Text, View } from "@tarojs/components";
import { useEffect, useRef, useState } from "react";
import "./swipe-card.css";

interface Photo {
  id: string;
  url: string;
  filename: string;
}

interface SwipeCardProps {
  photos: Photo[];
  onLike: (photo: Photo) => void;
  onDislike: (photo: Photo) => void;
  onComplete: () => void;
}

export function SwipeCard({ photos, onLike, onDislike, onComplete }: SwipeCardProps) {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [offsetX, setOffsetX] = useState(0);
  const [isAnimating, setIsAnimating] = useState(false);
  const startXRef = useRef(0);

  const currentPhoto = photos[currentIndex];
  const isComplete = currentIndex >= photos.length;

  useEffect(() => {
    if (isComplete) {
      onComplete();
    }
  }, [isComplete, onComplete]);

  const handleTouchStart = (e: any) => {
    startXRef.current = e.touches[0].clientX;
  };

  const handleTouchMove = (e: any) => {
    if (isAnimating) return;
    const currentX = e.touches[0].clientX;
    const diff = currentX - startXRef.current;
    setOffsetX(diff);
  };

  const handleTouchEnd = () => {
    if (isAnimating) return;
    
    const threshold = 80;
    
    if (offsetX > threshold) {
      animateOut("like");
    } else if (offsetX < -threshold) {
      animateOut("dislike");
    } else {
      setOffsetX(0);
    }
  };

  const animateOut = (action: "like" | "dislike") => {
    setIsAnimating(true);
    const targetX = action === "like" ? 500 : -500;
    const step = action === "like" ? 30 : -30;
    
    let x = offsetX;
    const interval = setInterval(() => {
      x += step;
      setOffsetX(x);
      if ((action === "like" && x >= targetX) || (action === "dislike" && x <= targetX)) {
        clearInterval(interval);
        setOffsetX(0);
        setIsAnimating(false);
        
        if (action === "like") {
          onLike(currentPhoto);
        } else {
          onDislike(currentPhoto);
        }
        
        setCurrentIndex(currentIndex + 1);
      }
    }, 16);
  };

  const handleButtonClick = (action: "like" | "dislike") => {
    if (isAnimating || !currentPhoto) return;
    animateOut(action);
  };

  if (isComplete) {
    return (
      <View className="swipe-complete">
        <Text className="swipe-complete-title">参考方向已记录</Text>
        <Text className="swipe-complete-subtitle">已浏览 {photos.length} 张照片</Text>
      </View>
    );
  }

  const rotate = offsetX * 0.05;
  const opacity = Math.min(Math.abs(offsetX) / 100, 1);
  const likeOpacity = offsetX > 0 ? opacity : 0;
  const dislikeOpacity = offsetX < 0 ? opacity : 0;

  return (
    <View 
      className="swipe-card-container"
      onTouchStart={handleTouchStart}
      onTouchMove={handleTouchMove}
      onTouchEnd={handleTouchEnd}
    >
      <View 
        className="swipe-card"
        style={{ 
          transform: `translateX(${offsetX}px) rotate(${rotate}deg)`,
        }}
      >
        <Image
          src={currentPhoto.url}
          mode="aspectFill"
          className="swipe-card-image"
        />
        
        <View 
          className="swipe-like-badge"
          style={{ opacity: likeOpacity }}
        >
          <Text>保留</Text>
        </View>
        
        <View 
          className="swipe-dislike-badge"
          style={{ opacity: dislikeOpacity }}
        >
          <Text>略过</Text>
        </View>
        
        <View className="swipe-card-info">
          <Text className="swipe-card-filename">{currentPhoto.filename}</Text>
        </View>
      </View>
      
      <View className="swipe-actions">
        <View 
          className="swipe-action-btn swipe-dislike"
          onClick={() => handleButtonClick("dislike")}
        >
          <Text>略过</Text>
        </View>
        <View 
          className="swipe-action-btn swipe-like"
          onClick={() => handleButtonClick("like")}
        >
          <Text>保留</Text>
        </View>
      </View>
      
      <View className="swipe-hint">
        <Text>左滑略过 · 右滑保留</Text>
      </View>
    </View>
  );
}
