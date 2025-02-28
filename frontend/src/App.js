import React, { useState, useEffect, useRef } from "react";
import axios from "axios";
import "./App.css";

function App() {
  const [file, setFile] = useState(null);
  const fileInputRef = useRef(null);
  const [text, setText] = useState("");
  const [fontSize, setFontSize] = useState(11);
  const [filename, setFilename] = useState("");
  const [textMessage, setTextMessage] = useState("");
  const [selectedFile, setSelectedFile] = useState(null);
  const [popupMessage, setPopupMessage] = useState(null);
  const [popupType, setPopupType] = useState("success");
  const [showPopup, setShowPopup] = useState(false);

  const [selectedDrink, setSelectedDrink] = useState(null);
  const [galleryImages, setGalleryImages] = useState([]);
  const [selectedGalleryImage, setSelectedGalleryImage] = useState(null);
  const [isSvgDropped, setIsSvgDropped] = useState(false);

  axios.defaults.baseURL = "http://localhost:5001";

  useEffect(() => {
    const loadImages = async () => {
      const imageContext = require.context(
        "../public/gallery",
        false,
        /\.(svg)$/
      );
      const images = imageContext
        .keys()
        .map((image) => `/gallery/${image.replace("./", "")}`);
      setGalleryImages(images);
    };

    loadImages();
  }, []);

  const handleGallerySelection = async (image) => {
    setSelectedGalleryImage(image);
    try {
      const response = await fetch(image);
      const blob = await response.blob();
      const galleryFile = new File([blob], "Drop your SVG here", {
        type: "image/svg+xml",
      });
      setFile(galleryFile);
    } catch (error) {
      console.error("Error converting gallery image:", error);
    }
  };

  // Show popup message
  const showPopupMessage = (
    message = "Your order has been placed!",
    type = "success"
  ) => {
    setPopupMessage(message);
    setPopupType(type);
    setShowPopup(true);
    setTimeout(() => {
      setShowPopup(false);
      resetForm();
    }, 1000);
  };

  const resetForm = () => {
    setSelectedDrink(null);
    setText("");
    setFile(null);
    setFilename("");
    setTextMessage("");
    setSelectedFile(null);
    setSelectedGalleryImage(null);
  };

  const handleFileChange = (event) => {
    const selectedFile = event.target.files[0];
    setFile(selectedFile);
    setIsSvgDropped(true);
    setSelectedGalleryImage(null);
  };

  const handleDropZoneClick = () => {
    fileInputRef.current && fileInputRef.current.click();
  };

  const handleFileDrop = (event) => {
    event.preventDefault();
    const droppedFile = event.dataTransfer.files[0];
    if (droppedFile?.type === "image/svg+xml") {
      setFile(droppedFile);
      setIsSvgDropped(true);
      setSelectedGalleryImage(null);
      showPopupMessage("SVG file selected", "success");
    } else {
      showPopupMessage("Please upload a valid SVG file.", "error");
      setFile(null);
      setIsSvgDropped(false);
    }
  };

  const handleDrinkSelection = (drink) => {
    setSelectedDrink(drink);
  };

  // Handle dynamic text size based on input length
  const handleTextChange = (e) => {
    const newText = e.target.value;
    setText(newText);

    const length = newText.length;
    if (length <= 5) setFontSize(16);
    else if (length <= 6) setFontSize(12);
    else if (length <= 7) setFontSize(11);
    else if (length <= 8) setFontSize(10);
    else if (length > 8) setFontSize(8);
  };

  const handlePlaceOrder = async () => {
    console.log("Handle Place Order Triggered");

    if (!file || !text) {
      showPopupMessage(
        "Please upload an SVG file and enter text to place the order.",
        "error"
      );
      return;
    }
    const reader = new FileReader();
    reader.onload = async () => {
      const svgString = reader.result;

      const orderData = {
        svg: svgString,
        text: text,
        drink: selectedDrink,
      };

      try {
        // Send data to createOrder endpoint
        const response = await axios.post(`/createOrder`, orderData, {
          headers: {
            "Content-Type": "application/json",
            Accept: "application/json",
          },
        });
        console.log("Order Response:", response);
        showPopupMessage("Order placed successfully!", "success");
      } catch (error) {
        console.error("Error placing order:", error);
        showPopupMessage("Error placing order: " + error.message, "error");
      }
    };

    reader.onerror = () => {
      showPopupMessage("Error reading SVG file.", "error");
    };

    if (file) {
      reader.readAsText(file);
    }
  };

  return (
    <div
      style={{
        paddingLeft: "120px",
        paddingRight: "120px",
        paddingTop: "40px",
        paddingBottom: "40px",
      }}
    >
      {/* Overlay for blur effect */}
      {showPopup && (
        <div
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: "rgba(0, 0, 0, 0.5)",
            backdropFilter: "blur(5px)",
            zIndex: 999,
          }}
        />
      )}

      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          marginBottom: "5px",
        }}
      >
        <img
          src="/TUM_logo.svg"
          alt="TUM Logo"
          style={{ width: "100px", marginRight: "10px" }}
        />
        <h1>RobotBar</h1>
      </div>

      {/* Choose Your Drink Section */}
      <h2>Choose Your Drink</h2>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          gap: "10px",
          padding: "5px",
        }}
      >
        {["Drink 1", "Drink 2", "Drink 3", "Drink 4", "Drink 5"].map(
          (drink, index) => (
            <div
              key={index}
              style={{
                textAlign: "center",
                width: "36%",
                border: "1px solid #ccc",
                padding: "5px",
                borderRadius: "10px",
                backgroundColor: selectedDrink === drink ? "#d3e6ff" : "#fff",
              }}
              onClick={() => handleDrinkSelection(drink)}
            >
              <h3>{drink}</h3>
              <button
                style={{
                  backgroundColor: selectedDrink === drink ? "#3170b3" : "#ccc",
                  color: "white",
                  padding: "10px 40px",
                  cursor: "pointer",
                  border: "none",
                  borderRadius: "5px",
                }}
              >
                {selectedDrink === drink ? "Selected" : "Select"}
              </button>
            </div>
          )
        )}
      </div>

      {/* Choose your logo or drop your own */}
      <h2>Choose your Logo</h2>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          gap: "10px",
          padding: "5px",
        }}
      >
        <div
          style={{
            display: "flex",
            overflowX: "auto",
            maxWidth: "100%",
            padding: "10px",
            border: "1px solid #ccc",
            gap: "10px",
          }}
        >
          {galleryImages.map((image, index) => (
            <img
              key={index}
              src={image}
              alt={`SVG ${index + 1}`}
              style={{
                width: "90px",
                height: "90px",
                border:
                  selectedGalleryImage === image
                    ? "3px solid #3170b3"
                    : "1px solid #ccc",
                borderRadius: "5px",
                cursor: "pointer",
                padding: "5px",
                backgroundColor:
                  selectedGalleryImage === image ? "#d3e6ff" : "#fff",
              }}
              onClick={() => handleGallerySelection(image)}
            />
          ))}
        </div>
        <div
          style={{
            width: "48%",
            border: "2px dashed #ccc",
            padding: "20px",
            textAlign: "center",
          }}
          onDrop={handleFileDrop}
          onClick={handleDropZoneClick}
        >
          {file && file.name ? <p>{file.name}</p> : <p>Drop your SVG here</p>}
          <input
            type="file"
            ref={fileInputRef}
            style={{ display: "none" }}
            accept=".svg"
            onChange={handleFileChange}
          />
        </div>
      </div>

      {/* Text input for name */}
      <h2>Enter the Name</h2>
      <div
        style={{
          display: "flex",
          justifyContent: "center",
          padding: "5px",
        }}
      >
        <input
          type="text"
          value={text}
          onChange={handleTextChange}
          style={{
            fontSize: `${fontSize * 2}px`,
            width: "100%",
            padding: "5px",
            textAlign: "center",
            border: "2px dotted #ccc",
            outline: "none",
          }}
        />
      </div>

      {text.length > 10 && (
        <p style={{ color: "red", fontSize: "12px" }}>
          Warning: Text is too long!
        </p>
      )}

      {/* Place Order Button */}
      <div style={{ textAlign: "center", marginTop: "20px" }}>
        <button
          style={{
            padding: "20px 40px",
            backgroundColor: "#3170b3",
            color: "white",
            border: "none",
            borderRadius: "5px",
            cursor: "pointer",
            maxWidth: "100%",
          }}
          onClick={handlePlaceOrder}
        >
          Place an Order
        </button>
      </div>

      {showPopup && (
        <div
          style={{
            position: "fixed",
            top: "40%",
            left: "50%",
            transform: "translateX(-50%)",
            backgroundColor: "#1e90ff",
            color: "white",
            padding: "30px",
            borderRadius: "25px",
            boxShadow: "0px 0px 10px rgba(0, 0, 0, 0.3)",
            zIndex: 1000,
            textAlign: "center",
          }}
        >
          <h3>{popupMessage}</h3>
        </div>
      )}
    </div>
  );
}

export default App;
