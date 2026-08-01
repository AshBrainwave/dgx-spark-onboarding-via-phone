export const shouldUseBle = () => "bluetooth" in navigator && !/iPhone|iPad|iPod/i.test(navigator.userAgent);
