class Filter:
    """
    Simple parametric mean value filter

    The adjustable smallest and largest values are discarded and the mean value is calculated from the remaining values.
    """
    def __init__(self, cut=1, avg=2):
        """
        Init filter with setup

        :param cut: number of values to discard
        :param avg: number of values for averaging
        """
        self.buf = []   # sample buffer
        self.cut = cut  # number of lowest and highest values to discard
        self.avg = avg  # number of values for averaging

    def __call__(self, input):
        """
        Filter

        :param input: raw value
        :return: filtered val
        """
        if isinstance(input, (int, float)):
            self.buf.append(input)

        self.buf = self.buf[-(2 * self.cut + self.avg):]  # limit to filterlength

        if len(self.buf) > (2 * self.cut):  # with sufficient values
            flt = sorted(self.buf)[self.cut:-self.cut]  # cut min and max
            return round(sum(flt) / len(flt))  # average values
        elif len(self.buf) > 0:
            return round(sum(self.buf) / len(self.buf))  # only average for to short buffer
        else:
            return 0
