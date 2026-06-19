export default defineAppConfig({
  pages: [
    "pages/swipe/index",
    "pages/login/index",
    "pages/shoot/index",
    "pages/album/index",
    "pages/edit/index",
    "pages/preference/index",
    "pages/retouch/index",
    "pages/complete/index",
  ],
  window: {
    navigationBarTitleText: "HelloBeauty",
    navigationBarBackgroundColor: "#F9F8F6",
    navigationBarTextStyle: "black",
    backgroundColor: "#F9F8F6",
    navigationStyle: "custom"
  },
  lazyCodeLoading: "requiredComponents",
  networkTimeout: {
    request: 20000,
    uploadFile: 20000,
    downloadFile: 20000,
  }
});
